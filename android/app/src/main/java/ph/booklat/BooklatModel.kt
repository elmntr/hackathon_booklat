package ph.booklat

import android.app.Application
import android.net.Uri
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import androidx.compose.runtime.*
import kotlinx.coroutines.*
import org.json.JSONObject
import java.io.File

class BooklatModel(app:Application):AndroidViewModel(app) {
    val store=Store(app); val prefs=app.getSharedPreferences("booklat",0); private val speech=Speech(app)
    var screen by mutableStateOf(prefs.getString("screen","landing")!!.let { if(it=="reading") "setup" else it })
    var passages by mutableStateOf<List<Passage>>(emptyList()); var selected by mutableStateOf<Passage?>(null)
    var learner by mutableStateOf(prefs.getString("learner","")!!)
    var history by mutableStateOf<List<Reading>>(emptyList()); var draft by mutableStateOf<Reading?>(null)
    var reading by mutableStateOf<Reading?>(null); var displayed by mutableStateOf<List<Mark>>(emptyList()); var provisional by mutableStateOf<Set<Int>>(emptySet()); var pointer by mutableIntStateOf(0)
    var busy by mutableStateOf(false); var active by mutableStateOf(false); var checking by mutableStateOf(false); var message by mutableStateOf(""); var status by mutableStateOf("")
    var elapsed by mutableIntStateOf(0); var level by mutableIntStateOf(0); var transcript by mutableStateOf("")
    var revision by mutableIntStateOf(0); var installed by mutableStateOf(mapOf("en" to false,"tl" to false))
    var installingLanguage by mutableStateOf<String?>(null); var installStage by mutableStateOf(""); var installProgress by mutableStateOf<Int?>(null)
    var mode by mutableStateOf(prefs.getString("mode","live")!!); var delay by mutableIntStateOf(prefs.getInt("delay",2))
    var autosave by mutableStateOf(prefs.getBoolean("autosave",true)); var record by mutableStateOf(prefs.getBoolean("record",true)); var follow by mutableStateOf(prefs.getBoolean("follow",true)); var colors by mutableStateOf(prefs.getBoolean("colors",true)); var diagnostics by mutableStateOf(false)
    var full by mutableStateOf(false); var focused by mutableStateOf(false); var size by mutableStateOf("32"); var editWord by mutableStateOf<Int?>(null)
    private var captureJob:Job?=null; private var finishJob:Job?=null; private var finishCancelled=false
    var finishing by mutableStateOf(false)
    init { task { refresh(); installed=Models.names.keys.associateWith { Models.installed(getApplication(),it) }; val prior=prefs.getString("result",null); reading=history.find { it.id==prior }; if(screen=="results"&&reading==null) screen="setup" } }
    suspend fun refresh() { val data=withContext(Dispatchers.IO){Triple(store.passages(),store.history(),store.draft())}; passages=data.first; history=data.second; draft=data.third; selected=passages.find { it.id==(selected?.id?:prefs.getString("passage",null)) }?:passages.firstOrNull() }
    fun task(block:suspend ()->Unit) { viewModelScope.launch { busy=true; message=""; try { block() } catch(e:Exception) { message=e.message?:"Operation failed." } finally { busy=false } } }
    fun preferences() { prefs.edit().putString("mode",mode).putInt("delay",delay).putBoolean("autosave",autosave).putBoolean("record",record).putBoolean("follow",follow).putBoolean("colors",colors).putString("learner",learner).putString("passage",selected?.id).apply() }
    fun navigate(to:String) { if(active||checking) stop(); screen=to; prefs.edit().putString("screen",to).apply() }
    fun select(p:Passage) { selected=p; preferences() }
    fun install(lang:String,uri:Uri?)=task {
        installingLanguage=lang;installStage="Preparing model…";installProgress=null
        try {
            withContext(Dispatchers.IO) {
                val app=getApplication<Application>()
                if(uri!=null) {
                    withContext(Dispatchers.Main){installStage="Installing ZIP…"}
                    app.contentResolver.openInputStream(uri)?.use { Models.install(app,lang,it) }?:error("Could not open the selected ZIP.")
                } else {
                    val archive=File(app.filesDir,"downloads/${Models.names.getValue(lang)}.zip")
                    val needed=if(lang=="tl") 1_300_000_000L-archive.length() else 200_000_000L-archive.length()
                    require(android.os.StatFs(app.filesDir.path).availableBytes>needed){"Not enough free storage. ${if(lang=="tl") "Filipino needs about 1.3 GB" else "English needs about 200 MB"} to download and install."}
                    val url=java.net.URL("https://alphacephei.com/vosk/models/${Models.names.getValue(lang)}.zip")
                    var shown=-1
                    withContext(Dispatchers.Main){installStage="Downloading ${if(lang=="en") "English" else "Filipino"}…"}
                    Models.download(url,archive) { bytes,total->
                        val percent=(bytes*100/total).toInt().coerceIn(0,100)
                        if(percent!=shown) { shown=percent;runBlocking(Dispatchers.Main){installProgress=percent} }
                    }
                    withContext(Dispatchers.Main){installStage="Unpacking and checking model…";installProgress=null}
                    archive.inputStream().use { Models.install(app,lang,it) }
                    archive.delete()
                }
            }
            installed=Models.names.keys.associateWith { Models.installed(getApplication(),it) }
            installStage="Model installed. Ready offline."
        } finally {
            installingLanguage=null;installProgress=null
        }
    }
    fun open(r:Reading) { reading=r; displayed=r.marks.map { it.copy() }; pointer=r.score.attempted; navigate("results"); prefs.edit().putString("result",r.id).apply(); revision++ }
    fun discard()=task { withContext(Dispatchers.IO){store.draft()?.let { d->if(store.history().none { it.id==d.id }) store.deleteRecordings(d) };store.clearDraft()}; draft=null }
    fun recover(review:Boolean) { val r=draft?:return; learner=r.learner; selected=r.passage; mode=r.mode; reading=r; if(review) open(r) else start(true) }
    fun start(resume:Boolean=false) {
        if(active||busy||checking) return
        val p=selected?:return
        if(learner.isBlank()) { message="Enter a learner name."; return }
        if(installed[p.language]!=true) { message="Install the ${if(p.language=="en") "English" else "Filipino"} model in Settings."; return }
        val r=if(resume) reading?:return else Reading(p,learner.trim()).apply { mode=this@BooklatModel.mode }
        reading=r; displayed=r.marks.map { it.copy() }; active=true; busy=true; elapsed=0; message=""; status="Preparing microphone…"; screen="reading"; preferences(); prefs.edit().putString("screen","reading").apply()
        finishCancelled=false; val offset=if(resume) r.score.attempted else 0; val timeOffset=if(resume) r.last?:0.0 else 0.0
        val aligned=Aligner(p.tokens.drop(offset)); pointer=offset
        captureJob=viewModelScope.launch {
            val wav=if(record) File(getApplication<Application>().filesDir,"recordings/${r.id}/$timeOffset.wav") else null
            var failure:String?=null
            try {
                withContext(Dispatchers.IO) {
                    store.draft(r)
                    speech.capture(p.language,wav,onReady={ viewModelScope.launch { busy=false; status="Listening" } },onFrame={json,final,end->
                        val raw=json.optJSONArray("result"); val text=json.optString(if(final) "text" else "partial")
                        val words=if(final) {
                            require(text.isEmpty()||raw!=null){"Recognizer returned words without timestamps."}
                            if(raw==null) emptyList() else List(raw.length()) { val w=raw.getJSONObject(it); Heard(w.getString("word"),w.getDouble("start"),w.getDouble("end")) }
                        } else { val tokens=text.split(' ').filter { it.isNotBlank() }; val start=aligned.last?:0.0; val step=maxOf(0.0,end-start)/maxOf(1,tokens.size); tokens.mapIndexed { i,w->Heard(w,start+i*step,start+(i+1)*step) } }
                        val next=if(final) aligned else aligned.copy(); next.feed(words)
                        // Marshal snapshots to the main thread; the worker never mutates UI state.
                        val snapshot=next.marks.map { it.copy(t0=it.t0?.plus(timeOffset),t1=it.t1?.plus(timeOffset)) }; val position=next.pointer+offset; val first=aligned.first?.plus(timeOffset); val last=aligned.last?.plus(timeOffset)
                        runBlocking(Dispatchers.Main) {
                            transcript=text; elapsed=end.toInt(); pointer=position
                            if(final) { r.marks=r.marks.mapIndexed { i,m->if(i<offset||i in r.locked) m else snapshot[i-offset] }; r.first=r.first?:first; r.last=last?:r.last }
                            displayed=r.marks.mapIndexed { i,m->if(i<offset||i in r.locked||final) m.copy() else snapshot[i-offset] }
                            provisional=if(final) emptySet() else displayed.indices.filter { displayed[it]!=r.marks[it] }.toSet()
                            if(final) { val draftJson=r.json().toString(); withContext(Dispatchers.IO) { store.draft(Reading.from(JSONObject(draftJson))) } }
                            if(text.isNotBlank()) { finishJob?.cancel(); finishing=false }
                            val tail=snapshot.lastOrNull()
                            if(r.mode=="auto_finish"&&!finishCancelled&&final&&position>=p.tokens.size&&tail?.status=="correct"&&tail.t1!=null) {
                                finishing=true; finishJob=viewModelScope.launch { delay(this@BooklatModel.delay*1000L); stop() }
                            }
                            revision++
                        }
                    },onLevel={v->viewModelScope.launch { level=v }})
                }
            } catch(e:Exception) { failure=e.message?:"Microphone stopped." }
            finally {
                finishJob?.cancel(); finishing=false; active=false; busy=false; provisional=emptySet(); displayed=r.marks.map { it.copy() }; status=""; full=false
                if(failure!=null) message="$failure Confirmed words are recoverable."
                withContext(Dispatchers.IO) { store.draft(r); if(autosave&&failure==null) { store.save(r); store.clearDraft() } }
                refresh(); open(r)
            }
        }
    }
    fun keepReading() { finishCancelled=true; finishing=false; finishJob?.cancel() }
    fun stop() { speech.stop(); finishJob?.cancel() }
    fun background() { if(active||checking) { message="Recording stopped when Booklat left the foreground."; stop() } }
    fun micCheck() {
        if(checking) { stop(); return }; if(active||busy) return
        checking=true; message=""; status="Checking microphone…"
        captureJob=viewModelScope.launch {
            try { withContext(Dispatchers.IO) { speech.capture(null,null,{}, {_,_,_->}, {v->viewModelScope.launch { level=v; status="Input level: $v%" }}) } }
            catch(e:Exception) { message=e.message?:"Microphone unavailable." }
            finally { checking=false; level=0; status="Microphone check stopped." }
        }
    }
    fun correct(action:String) { val r=reading?:return; val i=editWord?:return
        val m=displayed.getOrElse(i){r.marks[i]}.manual(action)
        r.locked.add(i); r.marks=r.marks.toMutableList().apply { set(i,m) }; displayed=displayed.toMutableList().apply { set(i,m) }; revision++; editWord=null
        task { withContext(Dispatchers.IO) { if(active) store.draft(r) else if(autosave) store.save(r) }; refresh() }
    }
    fun save()=task { val r=reading?:return@task; withContext(Dispatchers.IO){store.save(r);store.clearDraft()}; refresh(); message="Reading saved." }
    override fun onCleared() { stop(); super.onCleared() }
}
