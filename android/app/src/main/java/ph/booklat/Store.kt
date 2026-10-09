package ph.booklat

import android.content.Context
import android.content.ContentValues
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

class Store(val context:Context):SQLiteOpenHelper(context,"booklat.db",null,1) {
    override fun onCreate(db:SQLiteDatabase) { db.execSQL("CREATE TABLE passages(id TEXT PRIMARY KEY, document TEXT NOT NULL)"); db.execSQL("CREATE TABLE readings(id TEXT PRIMARY KEY, document TEXT NOT NULL)"); db.execSQL("CREATE TABLE draft(id INTEGER PRIMARY KEY, document TEXT NOT NULL)") }
    override fun onUpgrade(db:SQLiteDatabase,oldVersion:Int,newVersion:Int) { error("Unsupported database version") }
    fun passages():List<Passage> {
        val a=JSONArray(context.assets.open("passages.json").bufferedReader().readText())
        val list=MutableList(a.length()){Passage.from(a.getJSONObject(it))}
        readableDatabase.rawQuery("SELECT document FROM passages ORDER BY rowid",null).use { while(it.moveToNext()) list.add(Passage.from(JSONObject(it.getString(0)))) }; return list
    }
    fun add(p:Passage) { writableDatabase.insertOrThrow("passages",null,ContentValues().apply { put("id",p.id); put("document",p.json().toString()) }) }
    fun save(r:Reading) { writableDatabase.insertWithOnConflict("readings",null,ContentValues().apply { put("id",r.id); put("document",r.json().toString()) },SQLiteDatabase.CONFLICT_REPLACE) }
    fun history()=buildList { readableDatabase.rawQuery("SELECT document FROM readings ORDER BY rowid DESC",null).use { while(it.moveToNext()) add(Reading.from(JSONObject(it.getString(0)))) } }
    fun draft(r:Reading) { writableDatabase.insertWithOnConflict("draft",null,ContentValues().apply { put("id",1); put("document",r.json().toString()) },SQLiteDatabase.CONFLICT_REPLACE) }
    fun draft():Reading?=readableDatabase.rawQuery("SELECT document FROM draft WHERE id=1",null).use { if(it.moveToFirst()) Reading.from(JSONObject(it.getString(0))) else null }
    fun clearDraft() { writableDatabase.delete("draft",null,null) }
    fun recordings(r:Reading):List<File> = File(context.filesDir,"recordings/${r.id}").listFiles()?.filter { it.extension=="wav" }?.sortedBy { it.nameWithoutExtension.toDoubleOrNull()?:0.0 }?:emptyList()
    fun deleteRecordings(r:Reading) { File(context.filesDir,"recordings/${r.id}").deleteRecursively() }
    fun exportFile(name:String)=File(context.cacheDir,"exports/$name").also { it.parentFile!!.mkdirs() }
    fun csv():File {
        fun cell(s:Any?):String { val text=s?.toString()?:""; val safe=if(text.trimStart().firstOrNull() in listOf('=','+','-','@','\t','\r')) "'$text" else text; return "\"${safe.replace("\"","\"\"")}\"" }
        return exportFile("booklat-history.csv").apply { bufferedWriter().use { out ->
            out.write("Learner,Passage,Date,Attempted,Correct,Substitutions,Omissions,Repetitions,Accuracy,Seconds,WPM,Word category,Phil-IRI word score,Phil-IRI word level,Reviewed miscues,Comprehension correct,Questions,Comprehension percent,Comprehension level\r\n")
            history().forEach { r-> val s=r.score; out.write(listOf(r.learner,r.passage.title,r.timestamp,s.attempted,s.correct,s.substitutions,s.omissions,s.repetitions,s.accuracy,s.duration,s.wpm,s.level,r.wordPercent?.let { rounded(it,2) },if(s.partial) null else category(r.wordPercent),r.reviewed,r.answers,r.questions,r.comprehension?.let { rounded(it,2) },category(r.comprehension,80.0,59.0)).joinToString(","){cell(it)}+"\r\n") }
        } }
    }
    fun report(r:Reading):File {
        fun esc(s:Any?)=(s?.toString()?:"Not available").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace("\"","&quot;")
        val s=r.score
        return exportFile("booklat-report.html").apply { writeText("""<!doctype html><html lang="en"><meta charset="utf-8"><title>Booklat reading report</title><style>body{font:18px sans-serif;max-width:850px;margin:40px auto;color:#252c2a;background:#fafbf8}td,th{padding:12px;text-align:left;border-bottom:1px solid #d7ded7}</style><h1>Booklat reading report</h1><h2>${esc(r.learner)}</h2><p>${esc(r.passage.title)} / ${esc(r.timestamp)}</p><table><tr><th>Time</th><td>${esc(s.duration)} seconds</td></tr><tr><th>Words per minute</th><td>${esc(s.wpm)}</td></tr><tr><th>Accuracy</th><td>${esc(s.accuracy)}%</td></tr><tr><th>Word-reading category</th><td>${esc(s.level)}</td></tr><tr><th>Phil-IRI word score</th><td>${esc(r.wordPercent?.let { rounded(it,2) })}%</td></tr><tr><th>Word component</th><td>${esc(if(s.partial) "Incomplete reading" else category(r.wordPercent))}</td></tr><tr><th>Reviewed miscues</th><td>${esc(r.reviewed)}</td></tr><tr><th>Comprehension</th><td>${esc(r.answers)} / ${esc(r.questions)} (${esc(r.comprehension?.let { rounded(it,2) })}%)</td></tr><tr><th>Comprehension component</th><td>${esc(category(r.comprehension,80.0,59.0))}</td></tr></table><p>Component profile only. No overall placement. Comprehension is entered by a teacher, not inferred from speech. ${if(r.reviewed==null) "Automatic miscue estimate requires teacher review." else "Teacher-reviewed miscue total."}</p><p>Phil-IRI 2018 component criteria: word reading 97/90, comprehension 80/59. Partial readings have no word component level.</p><h2>Word marks</h2><ol>${r.passage.tokens.mapIndexed { i,w-> "<li>${esc(w)}: ${esc(r.marks[i].status)}, repeats ${r.marks[i].repeats}${if(r.marks[i].selfCorrected) ", self-corrected" else ""}</li>" }.joinToString("")}</ol></html>""") }
    }
    fun backup():File=exportFile("booklat-backup.zip").apply { ZipOutputStream(outputStream()).use { zip->
        fun entry(name:String,bytes:ByteArray) { zip.putNextEntry(ZipEntry(name)); zip.write(bytes); zip.closeEntry() }
        entry("booklat.json",JSONObject().put("version",1).put("passages",JSONArray(passages().map { it.json() })).put("readings",JSONArray(history().map { it.json() })).put("draft",draft()?.json()).put("preferences",JSONObject(context.getSharedPreferences("booklat",0).all)).toString(2).toByteArray())
        File(context.filesDir,"recordings").walkTopDown().filter { it.isFile && it.extension=="wav" }.forEach { entry("recordings/"+it.relativeTo(File(context.filesDir,"recordings")).path,it.readBytes()) }
    } }
}
