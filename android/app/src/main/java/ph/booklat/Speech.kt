package ph.booklat

import android.content.Context
import android.media.*
import org.vosk.Model
import org.vosk.Recognizer
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.io.InputStream
import java.io.RandomAccessFile
import java.net.HttpURLConnection
import java.net.URL
import java.util.zip.ZipInputStream
import java.util.concurrent.atomic.AtomicBoolean

object Models {
    val names=mapOf("en" to "vosk-model-small-en-us-0.15","tl" to "vosk-model-tl-ph-generic-0.6")
    fun directory(c:Context,lang:String)=File(c.filesDir,"models/${names.getValue(lang)}")
    fun installed(c:Context,lang:String)=File(directory(c,lang),"am/final.mdl").isFile
    fun download(url:URL,file:File,onProgress:(Long,Long)->Unit) {
        file.parentFile?.mkdirs()
        var failure:Exception?=null
        repeat(4) { attempt->
            val start=file.length()
            val connection=(url.openConnection() as HttpURLConnection).apply {
                connectTimeout=30000; readTimeout=60000; instanceFollowRedirects=true
                if(start>0) setRequestProperty("Range","bytes=$start-")
            }
            try {
                val code=connection.responseCode
                if(code==416) {
                    val total=connection.getHeaderField("Content-Range")?.substringAfter("*/")?.toLongOrNull()
                    if(total!=null&&start==total) { onProgress(start,total);return }
                    file.delete()
                    throw java.io.IOException("Saved download no longer matches the server; restarting.")
                }
                require(code==200||code==206){"Model download failed (HTTP $code)."}
                val range=connection.getHeaderField("Content-Range")
                val resumed=code==206&&range?.startsWith("bytes $start-")==true
                if(code==206&&!resumed) { file.delete();throw java.io.IOException("Model server returned an invalid download range.") }
                val total=if(resumed) range!!.substringAfter('/').toLongOrNull()?:-1L else connection.contentLengthLong
                require(total in 1..(1024L*1024*1024)){"Model download size is unavailable or too large."}
                if(!resumed) file.writeBytes(byteArrayOf())
                connection.inputStream.use { input->FileOutputStream(file,true).use { out->
                    val buffer=ByteArray(65536);var saved=file.length();onProgress(saved,total)
                    while(true) { val n=input.read(buffer);if(n<0) break;out.write(buffer,0,n);saved+=n;onProgress(saved,total) }
                } }
                if(file.length()!=total) throw java.io.IOException("Model download stopped early.")
                return
            } catch(e:java.io.IOException) {
                failure=e
                if(attempt==3) throw java.io.IOException("Download interrupted. Tap Download to resume (${e.message}).",e)
            } finally { connection.disconnect() }
        }
        throw failure?:java.io.IOException("Model download failed.")
    }
    fun install(c:Context,lang:String,input:InputStream) {
        val dest=directory(c,lang); val staging=File(dest.parentFile,"install-${java.util.UUID.randomUUID()}"); staging.mkdirs()
        try {
            var total=0L; var count=0
            ZipInputStream(input).use { zip->while(true) {
                val entry=zip.nextEntry?:break; require(++count<=20000){"Too many model files."}
                val file=File(staging,entry.name); require(file.canonicalPath.startsWith(staging.canonicalPath+File.separator)){"Unsafe model archive path."}
                if(entry.isDirectory) file.mkdirs() else { file.parentFile!!.mkdirs(); file.outputStream().use { out-> val buffer=ByteArray(65536); while(true) { val n=zip.read(buffer); if(n<0) break; total+=n; require(total<=2L*1024*1024*1024){"Model exceeds 2 GB."}; out.write(buffer,0,n) } } }
            } }
            val modelRoot=staging.walkTopDown().maxDepth(3).firstOrNull { it.isDirectory&&File(it,"am/final.mdl").isFile&&File(it,"conf/model.conf").isFile }?:error("ZIP does not contain a Vosk model.")
            val previous=File(dest.parentFile,"${dest.name}.previous"); previous.deleteRecursively()
            if(dest.exists()) check(dest.renameTo(previous)){"Cannot replace model."}
            if(!modelRoot.renameTo(dest)) { previous.renameTo(dest); error("Cannot install model.") }; previous.deleteRecursively()
        } finally { staging.deleteRecursively() }
    }
}
class WavWriter(file:File):AutoCloseable {
    private val out=RandomAccessFile(file,"rw"); private var bytes=0
    init { file.parentFile!!.mkdirs(); out.setLength(0); out.write(ByteArray(44)) }
    fun write(buffer:ShortArray,n:Int) { val b=ByteArray(n*2); for(i in 0 until n) { b[2*i]=(buffer[i].toInt() and 255).toByte(); b[2*i+1]=(buffer[i].toInt() shr 8).toByte() }; out.write(b); bytes+=b.size }
    override fun close() { out.seek(0); fun int(n:Int) { out.write(Integer.reverseBytes(n).let { java.nio.ByteBuffer.allocate(4).putInt(it).array() }) }; fun short(n:Int) { out.write(byteArrayOf(n.toByte(),(n shr 8).toByte())) }; out.writeBytes("RIFF"); int(36+bytes); out.writeBytes("WAVEfmt "); int(16); short(1); short(1); int(16000); int(32000); short(2); short(16); out.writeBytes("data"); int(bytes); out.close() }
}
class Speech(private val context:Context) {
    private val running=AtomicBoolean(false)
    @Volatile private var audio:AudioRecord?=null
    fun stop() { running.set(false); runCatching { audio?.stop() } }
    @Suppress("MissingPermission")
    fun capture(language:String?,wav:File?,onReady:()->Unit,onFrame:(JSONObject,Boolean,Double)->Unit,onLevel:(Int)->Unit) {
        check(running.compareAndSet(false,true)){"Microphone already in use."}
        var model:Model?=null; var recognizer:Recognizer?=null; var writer:WavWriter?=null
        val manager=context.getSystemService(AudioManager::class.java)
        val focus=AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT).setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_VOICE_COMMUNICATION).setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build()).setOnAudioFocusChangeListener { if(it<0) stop() }.build()
        try {
            if(language!=null) { model=Model(Models.directory(context,language).path); recognizer=Recognizer(model,16000f).also { it.setWords(true); it.setPartialWords(false) } }
            if(!running.get()) return
            check(manager.requestAudioFocus(focus)==AudioManager.AUDIOFOCUS_REQUEST_GRANTED){"Microphone interrupted by another app."}
            val minimum=AudioRecord.getMinBufferSize(16000,AudioFormat.CHANNEL_IN_MONO,AudioFormat.ENCODING_PCM_16BIT)
            check(minimum>0){"16 kHz recording is unavailable."}
            audio=AudioRecord(MediaRecorder.AudioSource.VOICE_RECOGNITION,16000,AudioFormat.CHANNEL_IN_MONO,AudioFormat.ENCODING_PCM_16BIT,maxOf(minimum*2,16000))
            check(audio!!.state==AudioRecord.STATE_INITIALIZED){"Cannot initialize microphone."}
            if(wav!=null) { wav.parentFile!!.mkdirs(); writer=WavWriter(wav) }
            audio!!.startRecording(); onReady(); val buffer=ShortArray(4000); var samples=0L
            while(running.get()) {
                val n=audio!!.read(buffer,0,buffer.size)
                if(!running.get()) break
                check(n>0){"Microphone disconnected or permission changed."}
                samples+=n; writer?.write(buffer,n)
                onLevel((kotlin.math.sqrt(buffer.take(n).sumOf { it.toDouble()*it }/n)/32768*100).toInt())
                recognizer?.let { r->val final=r.acceptWaveForm(buffer,n); onFrame(JSONObject(if(final) r.result else r.partialResult),final,samples/16000.0) }
            }
            recognizer?.let { onFrame(JSONObject(it.finalResult),true,samples/16000.0) }
        } finally {
            running.set(false); runCatching { audio?.stop() }; audio?.release(); audio=null; writer?.close(); recognizer?.close(); model?.close(); manager.abandonAudioFocusRequest(focus)
        }
    }
}
