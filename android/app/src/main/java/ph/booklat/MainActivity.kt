package ph.booklat

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.media.MediaPlayer
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.compose.BackHandler
import androidx.activity.SystemBarStyle
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.Alignment
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.*
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File

class MainActivity:ComponentActivity() {
    private val vm by viewModels<BooklatModel>()
    override fun onCreate(savedInstanceState:Bundle?) { super.onCreate(savedInstanceState); enableEdgeToEdge(statusBarStyle=SystemBarStyle.light(0xffeef1ed.toInt(),0xffeef1ed.toInt()),navigationBarStyle=SystemBarStyle.light(0xffeef1ed.toInt(),0xffeef1ed.toInt())); setContent { Booklat(vm) } }
    override fun onStop() { if(!isChangingConfigurations) vm.background(); super.onStop() }
}
@Composable fun Action(label:String,enabled:Boolean=true,onClick:()->Unit) { Button(onClick,enabled=enabled,shape=RoundedCornerShape(4.dp),contentPadding=PaddingValues(horizontal=16.dp,vertical=12.dp),modifier=Modifier.heightIn(min=48.dp)) { Text(label) } }
@Composable fun Field(label:String,value:String,onChange:(String)->Unit,numeric:Boolean=false) { OutlinedTextField(value,onChange,label={Text(label)},singleLine=true,keyboardOptions=KeyboardOptions(keyboardType=if(numeric) KeyboardType.Decimal else KeyboardType.Text),shape=RoundedCornerShape(4.dp),modifier=Modifier.fillMaxWidth()) }
@Composable fun Check(label:String,value:Boolean,change:(Boolean)->Unit) { Row(Modifier.fillMaxWidth().toggleableCompat(value,change),verticalAlignment=Alignment.CenterVertically) { Checkbox(value,change); Text(label,Modifier.weight(1f)) } }
fun Modifier.toggleableCompat(value:Boolean,change:(Boolean)->Unit)=this.clickable { change(!value) }.heightIn(min=48.dp)
@Composable fun Heading(text:String) { Text(text,fontSize=28.sp,fontWeight=FontWeight.Bold,modifier=Modifier.padding(vertical=8.dp)) }
@Composable fun Tupi(pose:String="welcome",height:Int=112) { val resource=when(pose){"listening"->R.drawable.tupi_listening;"cheering"->R.drawable.tupi_cheering;"encouraging"->R.drawable.tupi_encouraging;"supportive"->R.drawable.tupi_supportive;"nothing-heard"->R.drawable.tupi_nothing_heard;else->R.drawable.tupi_welcome}; Image(painterResource(resource),"Tupi, Booklat's bookmark",Modifier.height(height.dp).width((height*.85).dp)) }
@Composable fun Choice(label:String,value:String,options:List<Pair<String,String>>,select:(String)->Unit) { var open by remember { mutableStateOf(false) }; Column { Text(label,fontWeight=FontWeight.SemiBold); Box { OutlinedButton({open=true},shape=RoundedCornerShape(4.dp),modifier=Modifier.heightIn(min=48.dp)){Text(options.find { it.first==value }?.second?:value)}; DropdownMenu(open,{open=false}) { options.forEach { (key,name)->DropdownMenuItem(text={Text(name)},onClick={select(key);open=false}) } } } } }
@OptIn(ExperimentalLayoutApi::class)
@Composable fun Booklat(vm:BooklatModel) {
    val context=LocalContext.current
    var permissionAction by remember { mutableStateOf("start") }
    val permission=rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted->if(granted) when(permissionAction){"check"->vm.micCheck();"resume"->vm.recover(false);else->vm.start()} else vm.message="Microphone permission denied. Retry, or allow Microphone in Android app settings." }
    fun microphone(action:String) { permissionAction=action; if(ContextCompat.checkSelfPermission(context,Manifest.permission.RECORD_AUDIO)==PackageManager.PERMISSION_GRANTED) when(action){"check"->vm.micCheck();"resume"->vm.recover(false);else->vm.start()} else permission.launch(Manifest.permission.RECORD_AUDIO) }
    var modelLanguage by remember { mutableStateOf("en") }; val modelPicker=rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()){uri->if(uri!=null) vm.install(modelLanguage,uri)}
    var download by remember { mutableStateOf<String?>(null) }
    var player by remember { mutableStateOf<MediaPlayer?>(null) }; var playing by remember { mutableStateOf(false) }; var portion by remember(vm.reading?.id) { mutableIntStateOf(0) }
    fun playback(file:File,start:Double=0.0,end:Double?=null) { runCatching { player?.release(); player=MediaPlayer().apply { setDataSource(file.path); prepare(); seekTo((start*1000).toInt()); setOnCompletionListener { playing=false }; start() }; playing=true }.onFailure { vm.message="Cannot play recording: ${it.message}" } }
    DisposableEffect(vm.screen) { onDispose { player?.release(); player=null; playing=false } }
    fun share(file:File,mime:String) { val uri=FileProvider.getUriForFile(context,"${context.packageName}.exports",file); context.startActivity(Intent.createChooser(Intent(Intent.ACTION_SEND).setType(mime).putExtra(Intent.EXTRA_STREAM,uri).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION),"Save a copy")) }
    fun export(kind:String) { vm.task { val file=withContext(Dispatchers.IO) { when(kind){"csv"->vm.store.csv();"backup"->vm.store.backup();"report"->vm.store.report(vm.reading!!);else->vm.store.recordings(vm.reading!!)[portion].copyTo(vm.store.exportFile("booklat-recording.wav"),overwrite=true)} }; share(file,when(kind){"csv"->"text/csv";"backup"->"application/zip";"report"->"text/html";else->"audio/wav"}) } }
    BackHandler(vm.full||vm.screen!="landing") { when { vm.full->vm.full=false;vm.active->vm.stop();else->vm.navigate("setup".takeIf { vm.screen!="setup" }?:"landing") } }
    BooklatTheme {
        Surface(color=Mist,modifier=Modifier.fillMaxSize()) {
            Column(Modifier.safeDrawingPadding().imePadding().fillMaxSize()) {
                Row(Modifier.fillMaxWidth().padding(horizontal=16.dp,vertical=4.dp),verticalAlignment=Alignment.CenterVertically) {
                    TextButton({vm.navigate("landing")},enabled=!vm.active) { Row { Text("book",color=Vermilion,fontWeight=FontWeight.Black,fontSize=28.sp,textDecoration=TextDecoration.Underline,modifier=Modifier.graphicsLayer { rotationZ=-9f });Text("lat",color=Ink,fontWeight=FontWeight.Black,fontSize=28.sp) } }
                    Spacer(Modifier.weight(1f)); TextButton({vm.navigate("setup")},enabled=!vm.active){Text("Reading")}; TextButton({vm.navigate("settings")},enabled=!vm.active){Text("Settings")}
                }
                HorizontalDivider(color=Rule)
                if(vm.busy) LinearProgressIndicator(Modifier.fillMaxWidth().semantics { contentDescription="Working" })
                if(vm.message.isNotBlank()) Text(vm.message,color=Wine,modifier=Modifier.fillMaxWidth().padding(16.dp).semantics { liveRegion=LiveRegionMode.Polite })
                Box(Modifier.weight(1f).fillMaxWidth(),contentAlignment=Alignment.TopCenter) {
                    Column(Modifier.widthIn(max=1100.dp).fillMaxWidth().verticalScroll(rememberScrollState()).padding(20.dp),verticalArrangement=Arrangement.spacedBy(16.dp)) {
                        when(vm.screen) {
                            "landing" -> {
                                Heading("Assess oral reading."); Action("Prepare a reading"){vm.navigate("setup")}
                                Row(Modifier.fillMaxWidth().background(Chalk).padding(20.dp),verticalAlignment=Alignment.CenterVertically) { Column(Modifier.weight(1f)) { Text("Example reading",fontWeight=FontWeight.Bold);PassagePaper(listOf("Ben","reads","a","short","story","aloud."),listOf(Mark("correct"),Mark("correct"),Mark("correct"),Mark("omission"),Mark("substitution"),Mark("correct",1)),emptySet(),-1,24f,false,false,null) };Tupi() }
                                Heading("From passage to report."); Text("Choose a passage\nListen to the reading\nReview the marks",lineHeight=32.sp)
                                Heading("After the reading"); Text("Reading scores\nWord-by-word review\nVoice playback\nSaved readings",lineHeight=32.sp)
                                var about by remember { mutableStateOf(false) }; TextButton({about=!about}){Text("About Booklat")}; if(about) Text("Booklat helps teachers listen, track mistakes, time readings and review results. Offline speech recognition suggests word marks. Teachers review the marks and enter comprehension scores. Children's voices require teacher validation.")
                            }
                            "setup" -> {
                                Row(verticalAlignment=Alignment.CenterVertically){Text("Let’s hear you read.",Modifier.weight(1f),fontSize=30.sp,fontWeight=FontWeight.Bold);Tupi()}
                                Field("Learner name",vm.learner,{vm.learner=it.take(60);vm.preferences()})
                                PassagePicker(vm)
                                vm.selected?.let { p-> Row(verticalAlignment=Alignment.CenterVertically){ Text(p.title,Modifier.weight(1f),fontSize=22.sp,fontWeight=FontWeight.Bold);Action("Expand"){vm.full=true} }; PassagePaper(p.tokens,emptyList(),emptySet(),-1,24f,false,false,null) }
                                Action("Start reading",!vm.busy&&vm.learner.isNotBlank()){microphone("start")}
                                vm.draft?.let { d->Text("Unfinished reading: ${d.learner}, ${d.passage.title}"); FlowRow(horizontalArrangement=Arrangement.spacedBy(8.dp)){Action("Continue",!vm.busy&&d.score.attempted<d.marks.size){microphone("resume")};Action("Review draft"){vm.recover(true)};Action("Discard"){vm.discard()}} }
                                Action("Import passage",!vm.busy){vm.navigate("import")}
                                Heading("Reading history"); History(vm)
                                FlowRow(horizontalArrangement=Arrangement.spacedBy(8.dp)) { Action("Export CSV",!vm.busy){export("csv")};Action("Backup",!vm.busy){export("backup")} }
                            }
                            "reading" -> {
                                val r=vm.reading!!; Heading(r.passage.title)
                                Row(verticalAlignment=Alignment.CenterVertically){Tupi("listening",80); Column { Text(vm.status.ifBlank { "Listening" },modifier=Modifier.semantics { liveRegion=LiveRegionMode.Polite }); Text("${vm.pointer}/${r.marks.size} words    ${vm.elapsed / 60}:${(vm.elapsed%60).toString().padStart(2,'0')}") } }
                                FlowRow(horizontalArrangement=Arrangement.spacedBy(8.dp)){Action("Stop"){vm.stop()};Action("Expand"){vm.full=true};if(vm.finishing) Action("Keep reading"){vm.keepReading()}}
                                if(!vm.full) LivePassage(vm,24f)
                                if(vm.diagnostics) Text("Input ${vm.level}%\n${vm.transcript}\nConfirmed ${r.score.attempted} words",fontFamily=FontFamily.Monospace)
                            }
                            "results" -> vm.reading?.let { r->
                                val revision=vm.revision; val s=r.score
                                Heading("Reading results");Text("${r.learner} / ${r.passage.title}")
                                Row(verticalAlignment=Alignment.CenterVertically){Tupi(when(s.level){"independent"->"cheering";"instructional"->"encouraging";"frustration"->"supportive";else->"nothing-heard"});Column(Modifier.weight(1f)) {Text(s.level?.replaceFirstChar { it.uppercase() }?:"Nothing heard",fontSize=24.sp,fontWeight=FontWeight.Bold);Text("Time: ${s.duration?:"n/a"} s\nWords per minute: ${s.wpm?.toInt()?:"n/a"}\nAccuracy: ${s.accuracy?:"n/a"}%",lineHeight=30.sp)} }
                                if(s.partial) Text("Partial reading: ${s.attempted}/${s.total} words")
                                Action("Expand"){vm.full=true};if(!vm.full) PassagePaper(r.passage.tokens,r.marks,emptySet(),-1,24f,false,false,{vm.editWord=it})
                                val recordings=vm.store.recordings(r)
                                if(recordings.isNotEmpty()) {
                                    Heading("Voice recording"); if(recordings.size>1) Choice("Portion",portion.toString(),recordings.indices.map { it.toString() to "Portion ${it+1}" }) {portion=it.toInt();player?.release();player=null;playing=false}
                                    FlowRow(horizontalArrangement=Arrangement.spacedBy(8.dp)) {Action(if(playing) "Pause" else "Play"){if(playing){player?.pause();playing=false}else if(player!=null){player?.start();playing=true}else playback(recordings[portion.coerceIn(recordings.indices)])};Action("Export WAV",!vm.busy){export("wav")};Action("Delete recording",!vm.busy){player?.release();player=null;playing=false;vm.task { withContext(Dispatchers.IO){vm.store.deleteRecordings(r)};vm.revision++ }} }
                                }
                                Grading(vm,r)
                                FlowRow(horizontalArrangement=Arrangement.spacedBy(8.dp)){Action("Save result",!vm.busy){vm.save()};Action("Export report",!vm.busy){export("report")};Action("New reading"){vm.navigate("setup")}}
                            }
                            "settings" -> {
                                Heading("Settings")
                                Choice("When to show word validation",vm.mode,listOf("live" to "As I read","auto_finish" to "When reading finishes","after_pause" to "After a pause")){vm.mode=it;vm.preferences()}
                                Choice("Automatic finish delay",vm.delay.toString(),(1..3).map { it.toString() to "$it seconds" }){vm.delay=it.toInt();vm.preferences()}
                                Check("Keep the active line visible",vm.follow){vm.follow=it;vm.preferences()}
                                Heading("Microphone");Action(if(vm.checking) "Stop check" else "Check microphone",!vm.busy){microphone("check")};if(vm.status.isNotBlank()) Text(vm.status)
                                TextButton({context.startActivity(Intent(android.provider.Settings.ACTION_APPLICATION_DETAILS_SETTINGS,android.net.Uri.parse("package:${context.packageName}")))}){Text("Android app permissions")}
                                Heading("Offline models")
                                for(lang in listOf("en","tl")) { Text("${if(lang=="en") "English" else "Filipino"}: ${if(vm.installed[lang]==true) "Installed" else "Not installed"}",fontWeight=FontWeight.Bold);FlowRow(horizontalArrangement=Arrangement.spacedBy(8.dp)){Action("Download ${if(lang=="en") "English" else "Filipino"}",!vm.busy&&!vm.checking){download=lang};Action("Import ZIP",!vm.busy&&!vm.checking){modelLanguage=lang;modelPicker.launch(arrayOf("application/zip","application/octet-stream"))}} }
                                Heading("Saved readings");Check("Save completed readings",vm.autosave){vm.autosave=it;vm.preferences()};Check("Save voice recordings",vm.record){vm.record=it;vm.preferences()};Check("History category colors",vm.colors){vm.colors=it;vm.preferences()}
                                Check("Show speech diagnostics",vm.diagnostics){vm.diagnostics=it};Action("Back"){vm.navigate("setup")}
                            }
                            "import" -> ImportScreen(vm)
                        }
                    }
                }
            }
        }
        if(vm.full) Dialog({vm.full=false},properties=DialogProperties(usePlatformDefaultWidth=false)) {
            Surface(color=Chalk,modifier=Modifier.fillMaxSize().safeDrawingPadding()) { Column(Modifier.padding(16.dp),verticalArrangement=Arrangement.spacedBy(12.dp)) {
                FlowRow(horizontalArrangement=Arrangement.spacedBy(8.dp),verticalArrangement=Arrangement.spacedBy(8.dp)) {
                    Action("Collapse"){vm.full=false}; if(vm.active) Action("Stop"){vm.stop()}
                    Choice("Text size",vm.size,listOf("24" to "24","32" to "32","40" to "40","48" to "48","custom" to "Custom")){vm.size=it}
                }
                var custom by remember { mutableStateOf("32") };if(vm.size=="custom") Field("Custom text size",custom,{custom=it},true)
                val raw=if(vm.size=="custom") custom else vm.size; val size=raw.toFloatOrNull()?.takeIf { it.isFinite()&&it>0 }
                if(size==null) Text("Enter a positive decimal text size.",color=Wine)
                if(vm.screen=="reading") Check("Focused line",vm.focused){vm.focused=it}
                Box(Modifier.weight(1f).verticalScroll(rememberScrollState())) {
                    if(vm.screen=="reading") LivePassage(vm,size?:32f) else { val r=vm.reading.takeIf { vm.screen=="results" }; val p=r?.passage?:vm.selected; if(p!=null) PassagePaper(p.tokens,r?.marks?:emptyList(),emptySet(),-1,size?:32f,false,false,if(r!=null) { i->vm.editWord=i } else null) }
                }
            } }
        }
        vm.editWord?.let { i->val r=vm.reading!!; AlertDialog(onDismissRequest={vm.editWord=null},title={Text("Mark “${r.passage.tokens[i]}”")},text={Column {listOf("correct" to "Correct","substitution" to "Wrong","omission" to "Skipped","not_reached" to "Not read","repeat" to "Toggle repeated").forEach { (key,label)->TextButton({vm.correct(key)}){Text(label)} };if(!vm.active&&r.marks[i].t0!=null) { val start=r.marks[i].t0!!;val file=vm.store.recordings(r).lastOrNull { (it.nameWithoutExtension.toDoubleOrNull()?:0.0)<=start };if(file!=null) TextButton({playback(file,start-(file.nameWithoutExtension.toDoubleOrNull()?:0.0));vm.editWord=null}){Text("Play from word")} } }},confirmButton={TextButton({vm.editWord=null}){Text("Close")}},shape=RoundedCornerShape(8.dp),containerColor=Chalk,titleContentColor=Ink,textContentColor=Ink) }
        download?.let { lang->AlertDialog(onDismissRequest={download=null},title={Text("Install ${if(lang=="en") "English" else "Filipino"} model?")},text={Text(if(lang=="en") "Vosk small English 0.15. Apache 2.0. Download about 40 MB; allow 150 MB storage and about 300 MB runtime memory. Downloads from alphacephei.com only. Audio stays on this device." else "Vosk Filipino 0.6 by feddybear. CC BY-NC-SA 4.0, noncommercial use with attribution and share-alike. Download about 320 MB; allow 1 GB free storage and substantial runtime memory. Downloads from alphacephei.com only. Audio stays on this device.")},confirmButton={TextButton({download=null;vm.install(lang,null)}){Text("Download")}},dismissButton={TextButton({download=null}){Text("Cancel")}},shape=RoundedCornerShape(8.dp),containerColor=Chalk,titleContentColor=Ink,textContentColor=Ink) }
    }
}
