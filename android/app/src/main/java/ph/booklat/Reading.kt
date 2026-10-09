package ph.booklat

import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID
import kotlin.math.max
import kotlin.math.pow

fun rounded(n: Double, places: Int = 0): Double {
    val factor = 10.0.pow(places)
    return Math.rint(n * factor) / factor
}
data class Mark(var status: String = "not_reached", var repeats: Int = 0, var heard: String? = null, var t0: Double? = null, var t1: Double? = null, var selfCorrected: Boolean = false) {
    fun json() = JSONObject().put("status", status).put("repeats", repeats).put("heard", heard).put("t0", t0).put("t1", t1).put("self_corrected", selfCorrected)
    companion object { fun from(j: JSONObject) = Mark(j.getString("status"), j.optInt("repeats"), j.optString("heard").takeIf { it.isNotEmpty() }, if(j.has("t0")) j.getDouble("t0") else null, if(j.has("t1")) j.getDouble("t1") else null, j.optBoolean("self_corrected")) }
}
data class Passage(val id: String, val title: String, val language: String, val grade: Int, val text: String) {
    val tokens get() = text.trim().split(Regex("\\s+"))
    fun json() = JSONObject().put("id",id).put("title",title).put("language",language).put("grade",grade).put("text",text)
    companion object { fun from(j: JSONObject) = Passage(j.getString("id"),j.getString("title"),j.getString("language"),j.getInt("grade"),j.getString("text")) }
}
data class Heard(val text: String, val start: Double, val end: Double)
class Aligner(val tokens: List<String>) {
    var marks = tokens.map { Mark() }.toMutableList()
    var pointer = 0
    var first: Double? = null
    var last: Double? = null
    fun copy(): Aligner = Aligner(tokens).also { it.marks=marks.map { m->m.copy() }.toMutableList(); it.pointer=pointer; it.first=first; it.last=last }
    fun feed(words: List<Heard>) { words.forEach { w ->
        val h=normalize(w.text)
        if(h.isEmpty() || h in setOf("uh","um","ah","hmm","eh","oh","huh")) return@forEach
        if(first==null) first=w.start
        last=max(last?:w.end,w.end)
        fun mark(i:Int) { marks[i].apply { status="correct"; heard=w.text; t0=w.start; t1=w.end } }
        if(pointer<tokens.size && matches(h,tokens[pointer])) { mark(pointer++); return@forEach }
        val previous=(1..3).map { pointer-it }.firstOrNull { it>=0 && matches(h,tokens[it]) }
        if(previous!=null) { if(marks[previous].status=="substitution") { mark(previous); marks[previous].selfCorrected=true } else marks[previous].repeats++; return@forEach }
        val ahead=(1..3).map { pointer+it }.firstOrNull { it<tokens.size && matches(h,tokens[it]) }
        if(ahead!=null) { for(i in pointer until ahead) marks[i].status="omission"; mark(ahead); pointer=ahead+1 }
        else if(pointer<tokens.size) { marks[pointer++].apply { status="substitution"; heard=w.text; t0=w.start; t1=w.end } }
    } }
    companion object {
        fun normalize(s:String)=s.lowercase().filter { it.isLetterOrDigit() }
        fun matches(a:String,b:String):Boolean {
            val x=normalize(a); val y=normalize(b)
            if(x.isEmpty()||y.isEmpty()) return false
            if(minOf(x.length,y.length)<=3) return x==y
            // RapidFuzz ratio is normalized Indel similarity, equivalent to twice LCS.
            var row=IntArray(y.length+1)
            for(c in x) { val next=IntArray(y.length+1); for(j in y.indices) next[j+1]=if(c==y[j]) row[j]+1 else max(row[j+1],next[j]); row=next }
            return 200.0*row.last()/(x.length+y.length)>=80
        }
    }
}
fun Mark.manual(action:String):Mark=copy().apply {
    if(action=="repeat") repeats=if(repeats>0) 0 else 1
    else { require(action in setOf("correct","substitution","omission","not_reached")); status=action;selfCorrected=false;if(action=="not_reached") repeats=0 }
}
data class Score(val total:Int,val attempted:Int,val correct:Int,val substitutions:Int,val omissions:Int,val repetitions:Int,val miscues:Int,val accuracy:Double?,val duration:Double?,val wpm:Double?,val level:String?) {
    val partial get()=attempted<total
}
fun category(p:Double?, independent:Double=97.0,instructional:Double=90.0):String? = p?.let { if(it>=independent) "independent" else if(it>=instructional) "instructional" else "frustration" }
fun score(m:List<Mark>,first:Double?,last:Double?):Score {
    val attempted=m.indexOfLast { it.status!="not_reached" }+1; val reached=m.take(attempted)
    val correct=reached.count { it.status=="correct" }; val sub=reached.count { it.status=="substitution" }; val omit=reached.count { it.status=="omission" }; val rep=reached.sumOf { it.repeats }; val miscues=sub+omit+rep
    val accuracy=if(attempted>0) max(0.0,rounded((attempted-miscues)*100.0/attempted,1)) else null
    val duration=if(first!=null&&last!=null&&last>first) rounded(last-first,1) else null
    return Score(m.size,attempted,correct,sub,omit,rep,miscues,accuracy,duration,if(duration!=null&&duration>=1) rounded(correct*60/duration) else null,category(accuracy))
}
class Reading(val passage:Passage,var learner:String,val id:String=UUID.randomUUID().toString(),val timestamp:String=java.time.Instant.now().toString()) {
    var marks=passage.tokens.map { Mark() }; var first:Double?=null; var last:Double?=null
    var locked=mutableSetOf<Int>(); var reviewed:Int?=null; var answers:Int?=null; var questions:Int?=null; var mode="live"
    val score get()=score(marks,first,last)
    val wordPercent get()=if(score.attempted>0) max(0.0,(score.total-(reviewed?:score.miscues))*100.0/score.total) else null
    val comprehension get()=questions?.let { (answers?:0)*100.0/it }
    fun json()=JSONObject().put("id",id).put("timestamp",timestamp).put("passage",passage.json()).put("learner",learner).put("marks",JSONArray(marks.map { it.json() })).put("first",first).put("last",last).put("locked",JSONArray(locked.toList())).put("reviewed",reviewed).put("answers",answers).put("questions",questions).put("mode",mode)
    companion object { fun from(j:JSONObject)=Reading(Passage.from(j.getJSONObject("passage")),j.getString("learner"),j.getString("id"),j.getString("timestamp")).apply {
        marks=j.getJSONArray("marks").let { a-> List(a.length()){Mark.from(a.getJSONObject(it))} }; first=if(j.has("first")) j.getDouble("first") else null; last=if(j.has("last")) j.getDouble("last") else null
        locked=j.optJSONArray("locked")?.let { a->(0 until a.length()).map { a.getInt(it) }.toMutableSet() }?: mutableSetOf()
        reviewed=if(j.has("reviewed")) j.getInt("reviewed") else null; answers=if(j.has("answers")) j.getInt("answers") else null; questions=if(j.has("questions")) j.getInt("questions") else null; mode=j.optString("mode","live")
    } }
}
