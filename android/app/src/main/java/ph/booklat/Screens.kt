package ph.booklat

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.relocation.BringIntoViewRequester
import androidx.compose.foundation.relocation.bringIntoViewRequester
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.Alignment
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.*
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.util.UUID

@Composable fun PassagePicker(vm:BooklatModel) {
    var query by remember { mutableStateOf("") };var open by remember { mutableStateOf(false) }
    Text("Passages",fontWeight=FontWeight.Bold)
    OutlinedTextField(query,{query=it;open=true},label={Text("Search titles")},trailingIcon={TextButton({open=!open}){Text(if(open) "Close" else "Choose")}},modifier=Modifier.fillMaxWidth(),singleLine=true)
    if(open) { val choices=vm.passages.filter { it.title.contains(query,true) };if(choices.isEmpty()) Text("No matching passages.") else LazyColumn(Modifier.fillMaxWidth().heightIn(max=224.dp).background(Chalk).border(1.dp,Rule)) { items(choices,key={it.id}) { p->TextButton({vm.select(p);open=false;query=""},modifier=Modifier.fillMaxWidth().heightIn(min=56.dp)){Text(p.title,Modifier.fillMaxWidth())} } } }
}
@Composable fun History(vm:BooklatModel) {
    var q by remember { mutableStateOf("") };Field("Search history",q,{q=it})
    val rows=vm.history.filter { it.learner.contains(q,true)||it.passage.title.contains(q,true) }
    if(rows.isEmpty()) Text("No saved readings.") else LazyColumn(Modifier.heightIn(max=288.dp).fillMaxWidth().background(Chalk)) { items(rows,key={it.id}) { r->
        val color=if(!vm.colors || r.teacherNonReader) Ink else when(r.score.level){"independent"->Green;"instructional"->Amber;"frustration"->Color(0xff5c3b77);else->Ink}
        Column(Modifier.fillMaxWidth().clickable { vm.open(r) }.padding(12.dp)) { Text(r.learner,color=color,fontWeight=FontWeight.Bold);Text(r.passage.title);Text("${r.score.accuracy?:"n/a"}% / ${if(r.teacherNonReader) "Non-Reader (teacher)" else r.score.level?:"Not assessed"}",color=color);HorizontalDivider(color=Rule) }
    } }
}
@Composable fun LivePassage(vm:BooklatModel,size:Float) {
    val r=vm.reading?:return
    val marks=when(r.mode){"auto_finish"->emptyList();"after_pause"->r.marks;else->vm.displayed}
    PassagePaper(r.passage.tokens,marks,if(r.mode=="live"||r.mode=="after_pause") vm.provisional else emptySet(),vm.pointer,size,vm.focused&&vm.full,vm.follow,if(r.mode=="auto_finish") null else { i->vm.editWord=i })
}
@OptIn(ExperimentalFoundationApi::class)
@Composable fun PassagePaper(tokens:List<String>,marks:List<Mark>,provisional:Set<Int>,pointer:Int,size:Float,focused:Boolean,follow:Boolean,edit:((Int)->Unit)?) {
    val measurer=rememberTextMeasurer();val density=LocalDensity.current
    BoxWithConstraints(Modifier.fillMaxWidth().background(Chalk).border(1.dp,Rule).padding(12.dp)) {
        val style=TextStyle(fontSize=size.sp,fontFamily=FontFamily.Serif,lineHeight=(size*1.6f).sp)
        val availableWidth=maxWidth; val width=with(density){availableWidth.toPx()}
        val widths=remember(tokens,size,density.fontScale){tokens.map { with(density){maxOf(48.dp.toPx(),measurer.measure(it,style).size.width+16.dp.toPx())} }}
        val lines=remember(tokens,width,widths){buildList<List<Int>> { var row=mutableListOf<Int>();var used=0f;tokens.indices.forEach { i->if(row.isNotEmpty()&&used+widths[i]>width){add(row);row=mutableListOf();used=0f};row.add(i);used+=widths[i] };if(row.isNotEmpty()) add(row) }}
        val active=lines.indexOfFirst { pointer.coerceAtMost(tokens.lastIndex) in it }.coerceAtLeast(0)
        Column(Modifier.fillMaxWidth()) {
            lines.forEachIndexed { line,indices->if(!focused||line==active) {
                val bring=remember { BringIntoViewRequester() }
                LaunchedEffect(active,follow) { if(follow&&line==active) bring.bringIntoView() }
                Row(Modifier.fillMaxWidth().bringIntoViewRequester(bring).drawBehind { drawLine(Rule,Offset(0f,this.size.height-1),Offset(this.size.width,this.size.height-1),1.dp.toPx()) },verticalAlignment=Alignment.CenterVertically) {
                    indices.forEach { i->val mark=marks.getOrNull(i)?:Mark();val color=when {i in provisional->Blue;mark.repeats>0->Amber;mark.status=="correct"->Green;mark.status=="substitution"->Wine;mark.status=="omission"->Color(0xff4c5555);else->Ink}
                        val bg=when {i in provisional->Color(0xffe0eafb);mark.repeats>0->Color(0xfff2e7b9);mark.status=="correct"->Color(0xffdcebdd);mark.status=="substitution"->Color(0xfff5dde6);mark.status=="omission"->Color(0xffe2e5e5);else->Color.Transparent}
                        val description="${tokens[i]}: ${if(i in provisional) "provisional, " else ""}${mark.status.replace('_',' ')}, repeated ${mark.repeats} times${if(mark.selfCorrected) ", self-corrected" else ""}"
                        Box(Modifier.width(with(density){widths[i].toDp()}.coerceAtMost(availableWidth)).heightIn(min=48.dp).padding(horizontal=2.dp).background(bg).then(if(i==pointer) Modifier.border(2.dp,Blue) else Modifier).then(if(edit!=null && !(i in provisional && mark.status=="not_reached")) Modifier.clickable { edit(i) } else Modifier).semantics(mergeDescendants=true){contentDescription=description;if(edit!=null && !(i in provisional && mark.status=="not_reached")) role=Role.Button}.drawBehind {
                            if(mark.status!="not_reached") { val y=this.size.height-4.dp.toPx();drawLine(color,Offset(3f,y),Offset(this.size.width-3,y),2.dp.toPx(),pathEffect=if(mark.status=="substitution"||i in provisional) PathEffect.dashPathEffect(floatArrayOf(3f,4f)) else null);if(mark.repeats>0) drawLine(color,Offset(3f,y-5),Offset(this.size.width-3,y-5),1.dp.toPx()) }
                        },contentAlignment=Alignment.Center) {
                            Text(tokens[i],style=style,color=color,textDecoration=if(mark.status=="omission") TextDecoration.LineThrough else null,modifier=Modifier.padding(horizontal=2.dp,vertical=6.dp).clearAndSetSemantics {})
                            if(mark.selfCorrected) Text("↻",fontSize=12.sp,color=Blue,modifier=Modifier.align(Alignment.TopEnd).clearAndSetSemantics {})
                        }
                    }
                }
            } }
        }
    }
}
@Composable fun Grading(vm:BooklatModel,r:Reading) {
    var miscues by remember(r.id){mutableStateOf(r.reviewed?.toString()?:"")};var answers by remember(r.id){mutableStateOf(r.answers?.toString()?:"")};var total by remember(r.id){mutableStateOf(r.questions?.toString()?:"")};var nonReader by remember(r.id){mutableStateOf(r.teacherNonReader)}
    var error by remember { mutableStateOf("") }
    Heading("Teacher grading")
    Field("Reviewed miscues",miscues,{miscues=it},true);Field("Correct answers",answers,{answers=it},true);Field("Questions administered",total,{total=it},true)
    Check("Teacher confirms Non-Reader",nonReader){nonReader=it}
    Action("Apply teacher review") {
        val m=miscues.toIntOrNull();val a=answers.toIntOrNull();val t=total.toIntOrNull()
        error=when {miscues.isNotBlank()&&(m==null||m !in 0..100000)->"Enter a whole miscue count from 0 to 100000.";answers.isBlank()!=total.isBlank()->"Enter both comprehension scores.";answers.isNotBlank()&&(a==null||t==null||t !in 1..1000||a !in 0..t)->"Correct answers must be from 0 to the question count (1 to 1000).";else->""}
        if(error.isEmpty()) {r.reviewed=m;r.answers=a;r.questions=t;r.teacherNonReader=nonReader;vm.revision++;if(vm.autosave)vm.save()}
    }
    if(error.isNotBlank()) Text(error,color=Wine)
    Text("Word score: ${r.wordPercent?.let { rounded(it,2) }?:"n/a"}%\nWord component: ${if(r.score.partial) "Incomplete reading" else category(r.wordPercent)?:"n/a"}\nComprehension: ${r.comprehension?.let { rounded(it,2) }?:"n/a"}%\nComprehension component: ${category(r.comprehension,80.0,59.0)?:"n/a"}",lineHeight=28.sp)
    Text(if(r.reviewed==null) "Automatic miscue estimate. Teacher review required." else "Teacher-reviewed miscue total.")
    if(r.teacherNonReader) Text("Non-Reader status confirmed by the teacher. The word score remains separate.")
    Text("Reading level: ${r.readingLevel?:"Not assessed"}. Uses the supplied adapted Phil-IRI rubric. Comprehension is entered by a teacher.")
}
@Composable fun ImportScreen(vm:BooklatModel) {
    val context=LocalContext.current
    var title by remember { mutableStateOf("") };var text by remember { mutableStateOf(TextFieldValue("")) };var language by remember { mutableStateOf("en") };var grade by remember { mutableStateOf("3") };var filename by remember { mutableStateOf("") }
    val picker=rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()){uri->if(uri!=null)vm.task { val result=withContext(Dispatchers.IO){Documents.extract(context,uri)};filename=result.first;title=filename.substringBeforeLast('.').take(100);text=TextFieldValue(result.second) } }
    Heading("Import passage");Action("Choose document",!vm.busy){picker.launch(arrayOf("text/plain","text/markdown","application/pdf","application/vnd.openxmlformats-officedocument.wordprocessingml.document","application/epub+zip","application/octet-stream"))};if(filename.isNotEmpty()) Text(filename)
    Field("Passage title",title,{title=it.take(100)});Choice("Language",language,listOf("en" to "English","tl" to "Filipino")){language=it};Field("Grade",grade,{grade=it},true)
    OutlinedTextField(text,{text=it},label={Text("Passage text")},modifier=Modifier.fillMaxWidth().heightIn(min=240.dp),supportingText={Text("${text.text.trim().split(Regex("\\s+")).count { it.isNotEmpty() }} words")})
    Action("Use selection",!text.selection.collapsed){text=TextFieldValue(text.text.substring(text.selection.min,text.selection.max))}
    Action("Save passage",!vm.busy) {
        val g=grade.toIntOrNull();val clean=text.text.trim().replace(Regex("\\s+")," ")
        if(title.isBlank()||g==null||g !in 1..12||clean.isBlank()||clean.length>100000) vm.message="Enter a title, grade 1-12 and passage text up to 100,000 characters."
        else vm.task { val p=Passage(UUID.randomUUID().toString(),title.trim(),language,g,clean);withContext(Dispatchers.IO){vm.store.add(p)};vm.refresh();vm.select(p);vm.navigate("setup") }
    }
    Action("Back"){vm.navigate("setup")}
}
