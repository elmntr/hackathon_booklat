package ph.booklat

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp

val Mist=Color(0xffeef1ed); val Chalk=Color(0xfffafbf8); val Ink=Color(0xff252c2a); val Vermilion=Color(0xffa33a26); val Rule=Color(0xffd7ded7)
val Green=Color(0xff245330); val Wine=Color(0xff872449); val Blue=Color(0xff254b7e); val Amber=Color(0xff68500c)
private val Muted=Color(0xff53605a); private val Line=Color(0xff7e8982)

private val booklatColors=lightColorScheme(
    primary=Vermilion,onPrimary=Chalk,primaryContainer=Color(0xfff4b39d),onPrimaryContainer=Ink,
    secondary=Blue,onSecondary=Chalk,secondaryContainer=Color(0xffe0eafb),onSecondaryContainer=Ink,
    tertiary=Green,onTertiary=Chalk,tertiaryContainer=Color(0xffdcebdd),onTertiaryContainer=Ink,
    error=Wine,onError=Chalk,errorContainer=Color(0xfff5dde6),onErrorContainer=Wine,
    background=Mist,onBackground=Ink,surface=Chalk,onSurface=Ink,
    surfaceVariant=Mist,onSurfaceVariant=Muted,surfaceTint=Color.Transparent,
    surfaceContainerLowest=Chalk,surfaceContainerLow=Chalk,surfaceContainer=Chalk,
    surfaceContainerHigh=Chalk,surfaceContainerHighest=Mist,
    inverseSurface=Ink,inverseOnSurface=Chalk,inversePrimary=Color(0xfff4b39d),
    outline=Line,outlineVariant=Rule,scrim=Ink
)
private val booklatShapes=Shapes(
    extraSmall=RoundedCornerShape(4.dp),small=RoundedCornerShape(4.dp),
    medium=RoundedCornerShape(6.dp),large=RoundedCornerShape(8.dp),extraLarge=RoundedCornerShape(8.dp)
)

@Composable fun BooklatTheme(content:@Composable ()->Unit) {
    MaterialTheme(colorScheme=booklatColors,shapes=booklatShapes,typography=Typography(),content=content)
}
