package ph.booklat
import org.junit.Test
import org.junit.Assert.*
class ReadingTest {
    private fun align(text:String):Aligner=Aligner("Mina has a small garden".split(' ')).apply { feed(text.split(' ').mapIndexed { i,w->Heard(w,i.toDouble(),i+.5) }) }
    @Test fun alignmentParity() {
        listOf("Mina has a small garden" to listOf("correct","correct","correct","correct","correct"),"Mina a small garden" to listOf("correct","omission","correct","correct","correct"),"Mina had a small garden" to listOf("correct","substitution","correct","correct","correct"),"Mina has" to listOf("correct","correct","not_reached","not_reached","not_reached")).forEach { (input,expected)->assertEquals(expected,align(input).marks.map { it.status }) }
    }
    @Test fun repeatAndSelfCorrection() { val a=align("Mina Mina had has");assertEquals(2,a.pointer);assertEquals(1,a.marks[0].repeats);assertTrue(a.marks[1].selfCorrected);assertEquals("correct",a.marks[1].status) }
    @Test fun ignoredAndFilipino() {assertEquals("ñasá",Aligner.normalize("Ña's-á!"));assertFalse(Aligner.matches("ng","ang"));val a=Aligner(listOf("mahal","na","mahal"));a.feed(listOf("um","mahal","na","mahal","zebra").mapIndexed { i,w->Heard(w,i.toDouble(),i+.5) });assertEquals(3,a.pointer);assertEquals(1.0,a.first!!,0.0) }
    @Test fun scoreParity() {val s=score(List(50){Mark("correct")}+List(15){Mark("substitution")},0.0,60.0);assertEquals(76.9,s.accuracy!!,0.0);assertEquals("frustration",s.level);val partial=score(List(9){Mark("correct")}+Mark("substitution")+List(10){Mark()},2.0,32.0);assertEquals(18.0,partial.wpm!!,0.0);assertTrue(partial.partial);assertEquals(90.0,partial.accuracy!!,0.0);assertNull(score(List(3){Mark()},null,null).accuracy);assertNull(score(listOf(Mark("correct")),0.0,.5).wpm) }
    @Test fun boundaryAndRepetition() {for((n,expected) in listOf(97 to "independent",90 to "instructional",89 to "frustration"))assertEquals(expected,score(List(n){Mark("correct")}+List(100-n){Mark("substitution")},0.0,60.0).level);assertEquals(0.0,score(listOf(Mark("correct",2)),0.0,2.0).accuracy!!,0.0);assertEquals(2.0,rounded(2.5),0.0) }
    @Test fun previewsDoNotCommit() {val a=align("Mina");val preview=a.copy();preview.feed(listOf(Heard("had",1.0,1.5)));assertEquals("not_reached",a.marks[1].status);assertEquals("substitution",preview.marks[1].status) }
    @Test fun correctionRules() { val mark=Mark("correct",2,selfCorrected=true);val notRead=mark.manual("not_reached");assertEquals(0,notRead.repeats);assertFalse(notRead.selfCorrected);assertEquals(0,mark.manual("repeat").repeats);assertEquals(1,mark.manual("repeat").manual("repeat").repeats);assertEquals(2,mark.repeats) }
    @Test fun persistenceAndGrading() {val r=Reading(Passage("id","Title","en",3,"one two"),"Learner");r.marks=listOf(Mark("correct"),Mark("substitution"));r.locked.add(1);r.reviewed=0;r.answers=4;r.questions=5;val copy=Reading.from(r.json());assertEquals(100.0,copy.wordPercent!!,0.0);assertEquals(80.0,copy.comprehension!!,0.0);assertTrue(1 in copy.locked);assertEquals("independent",category(copy.comprehension,80.0,59.0)) }
}
