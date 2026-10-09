package ph.booklat

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import com.tom_roush.pdfbox.android.PDFBoxResourceLoader
import com.tom_roush.pdfbox.pdmodel.PDDocument
import com.tom_roush.pdfbox.text.PDFTextStripper
import java.io.ByteArrayInputStream
import java.io.InputStream
import java.util.zip.ZipInputStream
import javax.xml.parsers.DocumentBuilderFactory
import org.w3c.dom.Element

object Documents {
    fun bounded(input:InputStream,limit:Int):ByteArray { val out=java.io.ByteArrayOutputStream(); val buf=ByteArray(8192); var total=0; while(true) { val n=input.read(buf); if(n<0) break; total+=n; require(total<=limit){"File exceeds the import size limit."}; out.write(buf,0,n) }; return out.toByteArray() }
    fun xml(bytes:ByteArray):org.w3c.dom.Document {
        require(!Regex("<!\\s*(DOCTYPE|ENTITY)",RegexOption.IGNORE_CASE).containsMatchIn(bytes.toString(Charsets.UTF_8))){"Unsupported XML declarations."}
        return DocumentBuilderFactory.newInstance().apply { isNamespaceAware=true; setFeature("http://xml.org/sax/features/external-general-entities",false); setFeature("http://xml.org/sax/features/external-parameter-entities",false) }.newDocumentBuilder().parse(ByteArrayInputStream(bytes))
    }
    fun elements(doc:org.w3c.dom.Document,tag:String):List<Element> = doc.getElementsByTagNameNS("*",tag).let { ns->List(ns.length){ns.item(it) as Element} }
    fun extract(context:Context,uri:Uri):Pair<String,String> {
        val name=context.contentResolver.query(uri,null,null,null,null)?.use { c->if(c.moveToFirst()) c.getString(c.getColumnIndexOrThrow(OpenableColumns.DISPLAY_NAME)) else "document.txt" }?:"document.txt"
        val bytes=context.contentResolver.openInputStream(uri)!!.use { bounded(it,10*1024*1024) }
        return name to extractBytes(context,bytes,name)
    }
    fun extractBytes(context:Context,bytes:ByteArray,name:String):String {
        require(bytes.isNotEmpty()&&bytes.size<=10*1024*1024){"Choose a nonempty file up to 10 MB."}
        val text=when(name.substringAfterLast('.').lowercase()) {
            "txt","md" -> bytes.toString(if(bytes.size>1&&((bytes[0]==(-1).toByte()&&bytes[1]==(-2).toByte())||(bytes[0]==(-2).toByte()&&bytes[1]==(-1).toByte()))) Charsets.UTF_16 else Charsets.UTF_8).removePrefix("\uFEFF")
            "pdf" -> { PDFBoxResourceLoader.init(context); PDDocument.load(bytes).use { doc->require(!doc.isEncrypted){"Use an unlocked PDF."}; require(doc.numberOfPages<=200){"Choose a PDF with at most 200 pages."}; PDFTextStripper().getText(doc) } }
            "docx","epub" -> {
                val files=mutableMapOf<String,ByteArray>(); var expanded=0
                ZipInputStream(ByteArrayInputStream(bytes)).use { zip->while(true) { val e=zip.nextEntry?:break; require(files.size<5000){"Too many document entries."}; if(!e.isDirectory) { val b=bounded(zip,30*1024*1024-expanded); expanded+=b.size; files[e.name]=b } } }
                if(name.endsWith(".docx",true)) elements(xml(files["word/document.xml"]?:error("Invalid DOCX")),"p").joinToString(" "){it.textContent}
                else {
                    val root=elements(xml(files["META-INF/container.xml"]?:error("Invalid EPUB")),"rootfile").first().getAttribute("full-path")
                    val packageDoc=xml(files[root]?:error("Missing EPUB package")); val items=elements(packageDoc,"item").associate { it.getAttribute("id") to it.getAttribute("href") }
                    elements(packageDoc,"itemref").filter { it.getAttribute("linear")!="no" }.joinToString(" ") { item->
                        val href=java.net.URLDecoder.decode(items[item.getAttribute("idref")]!!.substringBefore('#'),"UTF-8")
                        val path=java.nio.file.Paths.get(root).parent?.resolve(href)?.normalize()?.toString()?:href
                        val html=(files[path]?:error("Missing EPUB chapter")).toString(Charsets.UTF_8).replace(Regex("<(script|style)\\b[^>]*>.*?</\\1>",setOf(RegexOption.IGNORE_CASE,RegexOption.DOT_MATCHES_ALL)),"")
                        android.text.Html.fromHtml(html,android.text.Html.FROM_HTML_MODE_LEGACY).toString()
                    }
                }
            }
            else -> error("Supported files: TXT, Markdown, PDF, DOCX and EPUB.")
        }
        val clean=text.replace("\u0000","").replace("\u00ad","").replace(Regex("\\s+")," ").trim()
        require(clean.isNotEmpty()){ "No readable text found. Scanned PDFs need OCR first, or paste the text." }
        require(clean.length<=100000){"Document exceeds 100,000 characters. Import a shorter excerpt."}
        return clean
    }
}
