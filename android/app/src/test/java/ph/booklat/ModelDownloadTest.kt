package ph.booklat

import org.junit.Assert.*
import org.junit.Test
import java.net.ServerSocket
import kotlin.concurrent.thread

class ModelDownloadTest {
    @Test fun interruptedDownloadResumes() {
        val bytes=ByteArray(1024*128) { (it%251).toByte() }
        val server=ServerSocket(0)
        val worker=thread {
            repeat(2) { call->server.accept().use { socket->
                val reader=socket.getInputStream().bufferedReader()
                var range:String?=null
                while(true) { val line=reader.readLine()?:break;if(line.isEmpty()) break;if(line.startsWith("Range:",true)) range=line.substringAfter(':').trim() }
                val offset=if(call==0) 0 else range!!.removePrefix("bytes=").removeSuffix("-").toInt()
                val out=socket.getOutputStream()
                if(call==0) {
                    out.write("HTTP/1.1 200 OK\r\nContent-Length: ${bytes.size}\r\nConnection: close\r\n\r\n".toByteArray())
                    out.write(bytes,0,bytes.size/2)
                } else {
                    out.write("HTTP/1.1 206 Partial Content\r\nContent-Length: ${bytes.size-offset}\r\nContent-Range: bytes $offset-${bytes.lastIndex}/${bytes.size}\r\nConnection: close\r\n\r\n".toByteArray())
                    out.write(bytes,offset,bytes.size-offset)
                }
                out.flush()
            } }
        }
        val file=kotlin.io.path.createTempFile("booklat-model-", ".zip").toFile()
        try {
            file.delete()
            var complete=0L
            Models.download(java.net.URL("http://127.0.0.1:${server.localPort}/model.zip"),file) { saved,total->if(saved==total) complete=saved }
            assertArrayEquals(bytes,file.readBytes())
            assertEquals(bytes.size.toLong(),complete)
        } finally { file.delete();server.close();worker.join(1000) }
    }
}
