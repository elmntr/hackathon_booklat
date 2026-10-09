package ph.booklat
import org.junit.Test
import org.junit.Assert.*
import java.io.File
class AudioTest {
 @Test fun wavHeaderAndSamples() {
  val file=File.createTempFile("booklat-audio-test",".wav")
  try { WavWriter(file).use { it.write(shortArrayOf(0,32767,-32768),3) }; val b=file.readBytes();assertEquals(50,b.size);assertEquals("RIFF",String(b.copyOfRange(0,4)));assertEquals("WAVE",String(b.copyOfRange(8,12)));assertEquals(16000,(b[24].toInt() and 255)+((b[25].toInt() and 255) shl 8));assertEquals(6,b[40].toInt());assertEquals(0x7fff,((b[47].toInt() and 255) shl 8)+(b[46].toInt() and 255)) } finally { file.delete() }
 }
}
