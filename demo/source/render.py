"""Render a 57-second feature demo from the actual UI's synthetic session captures."""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import subprocess, math, wave, json
import numpy as np
ROOT=Path(__file__).resolve().parents[1]; A=ROOT/'assets'
W,H,FPS,DURATION=1920,1080,30,57
BG='#EEF1ED'; INK='#252C2A'; RED='#A33A26'; MUTED='#53605A'; PAPER='#FAFBF8'
font='/usr/share/fonts/TTF/DejaVuSans.ttf'; bold='/usr/share/fonts/TTF/DejaVuSans-Bold.ttf'
def f(n,b=False):return ImageFont.truetype(bold if b else font,n)
def txt(d,xy,s,size=24,color=INK,b=False):d.text(xy,s,font=f(size,b),fill=color)
def lines(d,x,y,ss,size=54,color=INK,gap=1.17,b=True):
 for s in ss:txt(d,(x,y),s,size,color,b);y+=size*gap
 return y
scenes=[
 (4,'landing','INTRO',['Oral reading.','Teacher-led.'],['Meet Booklat.','An offline reading assessor','for your classroom.'],'English + Filipino'),
 (4,'setup','01 / PREPARE',['Choose the','next reading.'],['Enter a learner’s name.','Select a passage.','Start when they are ready.'],'A familiar classroom workflow'),
 (4,'language','01 / PREPARE',['English or','Filipino.'],['Search the passage library','and choose the reading','for your learner.'],'Two languages. One workspace.'),
 (5,'import','02 / PERSONALIZE',['Bring your','own material.'],['Paste a passage or import','TXT, Markdown, PDF,','DOCX and EPUB.'],'Choose the language and grade'),
 (1,'read00','03 / READ',['See reading','word by word.'],['Marks follow the reading.','Spot correct words,','miscues and omissions.'],'Simulated recognizer events'),
 (1.5,'read8','03 / READ',['See reading','word by word.'],['Marks follow the reading.','Spot correct words,','miscues and omissions.'],'Simulated recognizer events'),
 (1.5,'read17','03 / READ',['See reading','word by word.'],['Marks follow the reading.','Spot correct words,','miscues and omissions.'],'Simulated recognizer events'),
 (1.5,'read26','03 / READ',['See reading','word by word.'],['Marks follow the reading.','Spot correct words,','miscues and omissions.'],'Simulated recognizer events'),
 (1.5,'read36','03 / READ',['See reading','word by word.'],['Marks follow the reading.','Spot correct words,','miscues and omissions.'],'Simulated recognizer events'),
 (1,'read48','03 / READ',['See reading','word by word.'],['Marks follow the reading.','Spot correct words,','miscues and omissions.'],'Simulated recognizer events'),
 (5,'expanded','04 / ENLARGE',['Make room','for reading.'],['Expand the passage.','Keep words clear and','easy to follow together.'],'Large passage view'),
 (4,'editor','05 / REVIEW',['Your judgment','has the','final word.'],['Select a suggested miscue.','Compare what was heard.','Choose the correct mark.'],'Mock correction: “garden”'),
 (4,'corrected','05 / REVIEW',['One correction.','Updated','results.'],['The teacher corrects','the suggested error.','Booklat updates the score.'],'Teacher corrections stay editable'),
 (6,'corrected','06 / UNDERSTAND',['Turn reading','into insight.'],['Review accuracy, pace','and the word-reading','category in one report.'],'Scores shown are mock results'),
 (6,'grading','07 / ASSESS',['Add your','teacher review.'],['Enter comprehension results.','Review component levels.','Download the grading report.'],'Phil-IRI component criteria'),
 (7,'history','08 / KEEP',['Keep the','reading story.'],['Reopen saved readings.','Export scores as CSV.','Back up library and history.'],'Saved locally on your computer')]
assert sum(s[0] for s in scenes)==57
images={p.stem:Image.open(p).convert('RGB') for p in A.glob('*.png')}
def intro_frame(t):
 im=Image.new('RGB',(W,H),BG);d=ImageDraw.Draw(im)
 u=min(1,t/.8);ease=1-(1-u)**3
 ox=240-420*(1-ease);oy=175-abs(math.sin(t*math.pi*2))*16*(1 if t<3 else .3);scale=4.3
 def pt(x,y):return (ox+x*scale,oy+y*scale)
 def line(points,color=INK,width=3):d.line([pt(*p) for p in points],fill=color,width=round(width*scale),joint='curve')
 # Legs and the welcoming arm use the original Booklat SVG coordinates.
 line([(53,124),(48,142),(36,142)]);line([(77,124),(85,142),(97,142)])
 line([(89,83),(106,68)])
 angle=math.sin(max(0,t-.65)*11)*.36 if t>.65 else 0
 def wave(x,y):
  a,b=x-40,y-82
  return (40+a*math.cos(angle)-b*math.sin(angle),82+a*math.sin(angle)+b*math.cos(angle))
 line([(40,82),wave(24,69),wave(20,52)])
 d.polygon([pt(*v) for v in [(43,26),(80,22),(94,44),(88,128),(65,113),(43,131)]],fill='#F4B39D')
 line([(43,26),(80,22),(94,44),(88,128),(65,113),(43,131),(43,26)],RED,2)
 d.polygon([pt(*v) for v in [(80,22),(78,45),(94,44)]],fill='#DE8264');line([(80,22),(78,45),(94,44)],RED,2)
 for x in [57,76]:
  if 2.35<t<2.48:line([(x-3,68),(x+3,68)],INK,2)
  else:d.ellipse([pt(x-3,65),pt(x+3,71)],fill=INK)
 smile=[(59+16*i/25,81+18*(i/25)*(1-i/25)) for i in range(26)];line(smile,INK,2.5)
 # The name settles into place as Tupi arrives and waves.
 nx=900+90*(1-ease)
 txt(d,(nx,366),'book',124,RED,True);width=d.textlength('book',font=f(124,True));txt(d,(nx+width,366),'lat',124,INK,True)
 txt(d,(nx+4,550),'Let’s hear you read.',40,INK)
 txt(d,(nx+4,620),'Offline oral-reading assessment',25,MUTED)
 return im
def base_scene(sc):
 dur,name,kicker,heads,body,foot=sc
 im=Image.new('RGB',(W,H),BG);d=ImageDraw.Draw(im)
 if kicker=='INTRO':
  return intro_frame(3.5)
 else:
  txt(d,(72,177),kicker,24,RED,True)
  y=lines(d,70,257,heads,51)
  lines(d,74,max(y+48,505),body,25,MUTED,gap=1.55,b=False)
  d.rectangle((74,803,118,809),fill=RED)
  # Wrap a long footer on the compact editorial rail.
  words=foot.split(); rows=[];row=''
  for word in words:
   if d.textlength((row+' '+word).strip(),font=f(21,True))>430:rows.append(row);row=word
   else:row=(row+' '+word).strip()
  rows.append(row);lines(d,74,832,rows,21,INK,gap=1.5)
  source=images[name]
  # The correction shot focuses on the actual editor; the score shot focuses on the actual report.
  if kicker=='05 / REVIEW' and name=='editor':source=source.crop((25,550,1255,900))
  if kicker=='06 / UNDERSTAND':source=source.crop((24,94,1256,651))
  if kicker=='08 / KEEP':source=source.crop((25,405,1255,875))
  x,y,w,h=572,148,1276,816
  d.rectangle((x+10,y+10,x+w+10,y+h+10),fill='#D8DED7')
  d.rectangle((x,y,x+w,y+h),fill=PAPER)
  sw,sh=source.size;scale=min(w/sw,h/sh)
  scaled=source.resize((round(sw*scale),round(sh*scale)),Image.Resampling.LANCZOS)
  px=x+(w-scaled.width)//2;py=y+(h-scaled.height)//2;im.paste(scaled,(px,py))
  d=ImageDraw.Draw(im);d.rectangle((x,y,x+w,y+h),outline='#ABB7AD',width=2)
  if sh<600:
   txt(d,(x+30,y+24),'BOOKLAT  /  '+('TEACHER REVIEW' if name=='editor' else 'READING REPORT' if kicker=='06 / UNDERSTAND' else 'OFFLINE HISTORY'),21,MUTED,True)
 return im
bases=[base_scene(s) for s in scenes]
for n,im in enumerate(bases):im.save(A/f'frame-{n:02}.jpg',quality=90)
# Separate existing content into layers so motion never moves a flattened scene.
def ease(t):return 1-(1-max(0,min(1,t)))**3
def background(index):
 if index==11:return '#111614'
 return ['#EEF1ED','#FAF9F3','#F1F3EE','#F7F0E9'][index%4] if not 4<=index<=9 else '#EEF1ED'
def key_layer(image,dark=False):
 arr=np.array(image.convert('RGBA'));mask=np.all(arr[:,:,:3]==np.array([238,241,237]),axis=2)
 arr[:,:,3][mask]=0
 if dark:
  # Preserve the vermilion chapter label; lighten ink and body text on the emphasis scene.
  ink=np.all(arr[:,:,:3]==[37,44,42],axis=2);muted=np.all(arr[:,:,:3]==[83,96,90],axis=2)
  arr[:,:,:3][ink]=[250,251,248];arr[:,:,:3][muted]=[198,210,203]
 return Image.fromarray(arr)
regions=[(64,165,530,220),(64,250,550,470),(64,490,550,660),(64,795,550,900)]
layers=[]
for i,sc in enumerate(scenes):
 _,_,kicker,heads,body,foot=sc
 overlay=Image.new('RGBA',(W,H),(0,0,0,0));dd=ImageDraw.Draw(overlay)
 ink=PAPER if i==11 else INK;muted='#C6D2CB' if i==11 else MUTED
 txt(dd,(72,177),kicker,24,'#EC947A' if i==11 else RED,True)
 y=lines(dd,70,257,heads,51,ink)
 lines(dd,74,max(y+48,505),body,25,muted,gap=1.55,b=False)
 dd.rectangle((74,803,118,809),fill=RED)
 rows=[];row=''
 for word in foot.split():
  candidate=(row+' '+word).strip()
  if dd.textlength(candidate,font=f(21,True))>430:rows.append(row);row=word
  else:row=candidate
 rows.append(row);lines(dd,74,832,rows,21,ink,gap=1.5)
 layers.append([(overlay.crop(box),box[:2]) for box in regions])
mockups=[b.crop((572,148,1860,976)).convert('RGBA') for b in bases]
def paste_motion(out,layer,pos,t,delay,direction,scale=False):
 progress=ease((t-delay)/.55)
 if progress<=0:return
 x,y=pos;part=layer
 if scale:
  z=.985+.015*progress;w,h=layer.size
  part=layer.resize((round(w*z),round(h*z)),Image.Resampling.BICUBIC)
  x+=(w-part.width)/2;y+=(h-part.height)/2
 x+=direction*30*(1-progress)
 if progress<1:part=part.copy();part.putalpha(part.getchannel('A').point(lambda a:round(a*progress)))
 out.paste(part,(round(x),round(y)),part)
def animated_scene(index,t):
 # Continuous word-mark updates form one reading shot, without restarting its entrance.
 if 5<=index<=9:return bases[index].copy()
 bg=Image.new('RGB',(W,H),background(index))
 if index and t<.55:
  prev=Image.new('RGB',(W,H),'#000000' if index==11 else background(index-1))
  bg=Image.blend(prev,bg,ease(t/.55))
 direction=1 if index%2 else -1
 if index==0:
  intro=intro_frame(max(0,t-.15))
  paste_motion(bg,key_layer(intro.crop((0,150,820,900))),(0,150),t,.15,-1)
  paste_motion(bg,key_layer(intro.crop((820,340,1740,530))),(820,340),t,.30,1)
  paste_motion(bg,key_layer(intro.crop((820,530,1740,700))),(820,530),t,.45,1)
  return bg
 mock=mockups[index].copy()
 if index==13:
  # Existing result panels reveal left-to-right, 150 ms apart.
  for k,(x1,x2) in enumerate([(16,507),(507,884),(884,1260)]):
   box=(x1,308,x2,568);card=mock.crop(box)
   fill=Image.new('RGBA',card.size,PAPER)
   mock.paste(Image.blend(fill,card,ease((t-.55-k*.15)/.45)),box[:2])
 paste_motion(bg,mock,(572,148),t,.15,direction,True)
 for k,(layer,pos) in enumerate(layers[index]):
  delay=[.30,.45,.60,.75][k]
  if index==15 and k==3 and t>4.5:
   # Fade in closing text inside the final history scene; do not restore the removed end card.
   closing=Image.new('RGBA',layer.size,(0,0,0,0));dd=ImageDraw.Draw(closing)
   txt(dd,(10,30),'Start with one reading.',27,RED,True)
   paste_motion(bg,closing,pos,t,4.5,direction)
  else:
   if index==15 and k==3 and t>3.95:
    layer=layer.copy();layer.putalpha(layer.getchannel('A').point(lambda a:round(a*(1-ease((t-3.95)/.55)))))
   paste_motion(bg,layer,pos,t,delay,direction)
 return bg
# Boundary checks for the timing contract.
assert ease(0)==0 and ease(1)==1 and .4<=.55<=.7
for i,t in [(0,.5),(1,.7),(11,1.4),(13,1.4),(15,5.5)]:
 animated_scene(i,t).save(A/f'motion-check-{i:02}.jpg',quality=92)
# Brighter 124 BPM major-key groove: plucked chords, bouncy bass, kick, clap and hats.
sr=44100; audio=np.zeros(sr*DURATION,dtype=np.float64);beat=60/124
rng=np.random.default_rng(42)
chords=[[60,64,67,72],[65,69,72,76],[67,71,74,79],[60,64,67,76]]
def note(start,midi,dur,amp):
 start=int(start*sr);N=min(int(dur*sr),len(audio)-start)
 if N<=0:return
 t=np.arange(N)/sr;hz=440*2**((midi-69)/12)
 env=(1-np.exp(-t*180))*np.exp(-t/0.23)*np.minimum(1,(N/sr-t)*30)
 tone=np.sin(2*np.pi*hz*t)+.36*np.sin(4*np.pi*hz*t)+.16*np.sin(6*np.pi*hz*t)
 audio[start:start+N]+=amp*tone*env

def drum(at,kind):
 start=int(at*sr);N=min(int(.20*sr),len(audio)-start)
 if N<=0:return
 t=np.arange(N)/sr
 if kind=='kick':v=np.sin(2*np.pi*(52*t+4*(1-np.exp(-t*35))))*np.exp(-t*23)*.30
 elif kind=='clap':
  noise=rng.normal(0,1,N);v=(noise-np.roll(noise,1))*.065*np.exp(-t*35)*(1-np.exp(-t*500))
 else:
  noise=rng.normal(0,1,N);v=(noise-np.roll(noise,1))*.022*np.exp(-t*90)
 audio[start:start+N]+=v
for bar in range(math.ceil(DURATION/(4*beat))):
 c=chords[bar%4];start=bar*4*beat
 for k in [0,1.5,2,3.5]:note(start+k*beat,c[0]-24,.38,.21)
 for k in [.5,1.5,2.5,3.5]:
  for pitch in c[:3]:note(start+k*beat,pitch,.42,.065)
 for k,pitch in enumerate([c[2]+12,c[1]+12,c[3],c[2]+12]):note(start+(k+.25)*beat,pitch,.32,.075)
 for k in [0,2]:drum(start+k*beat,'kick')
 for k in [1,3]:drum(start+k*beat,'clap')
 for k in range(8):drum(start+k*.5*beat,'hat')
audio*=np.minimum(1,np.arange(len(audio))/sr/1.2)*np.minimum(1,(len(audio)-np.arange(len(audio)))/sr/2)
audio=np.tanh(audio)*.60
stereo=np.stack([audio,np.roll(audio,int(sr*.009))*.97],axis=1)
with wave.open(str(ROOT/'soundtrack-upbeat.wav'),'wb') as wav:wav.setnchannels(2);wav.setsampwidth(2);wav.setframerate(sr);wav.writeframes((stereo*32767).astype('<i2').tobytes())
cmd=['ffmpeg','-hide_banner','-loglevel','warning','-y','-f','rawvideo','-vcodec','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-','-i',str(ROOT/'soundtrack-upbeat.wav'),'-c:v','libx264','-preset','fast','-crf','19','-threads','4','-pix_fmt','yuv420p','-af','loudnorm=I=-20:TP=-2:LRA=7','-c:a','aac','-b:a','192k','-t',str(DURATION),'-movflags','+faststart',str(ROOT/'Booklat-demo-v3-57s.mp4')]
p=subprocess.Popen(cmd,stdin=subprocess.PIPE);elapsed=0
for index,(sc,base) in enumerate(zip(scenes,bases)):
 n=round(sc[0]*FPS);print('Rendering',index,sc[2],flush=True)
 for j in range(n):
  t=j/FPS;im=animated_scene(index,t)
  d=ImageDraw.Draw(im)
  # A moving cursor and click ring indicate the point of interaction in the mock flow.
  target=None
  if sc[1]=='setup':target=(850,533)
  elif sc[1]=='language':target=(810,598)
  elif sc[1]=='import':target=(745,923)
  elif sc[1]=='editor':target=(988,677)
  elif sc[2]=='07 / ASSESS':target=(1220,640)
  elif sc[2]=='08 / KEEP':target=(1670,718)
  if target and t>1.15:
   u=min(1,(t-1.15)/.85);u=u*u*(3-2*u);x=target[0]+(1-u)*110;y=target[1]+(1-u)*60
   d.polygon([(x,y),(x+3,y+30),(x+11,y+23),(x+19,y+38),(x+26,y+34),(x+18,y+20),(x+30,y+19)],fill=INK,outline=PAPER,width=2)
   if 2.05<t<2.55:
    radius=12+35*(t-2.05)/.5;d.ellipse((x-radius,y-radius,x+radius,y+radius),outline=RED,width=3)
  # Soft departures create room for the next staggered entrance; reading remains continuous.
  continuous=4<=index<9
  if not continuous and index<len(scenes)-1 and t>sc[0]-.55:
   target_color='#000000' if index==10 else background(index)
   im=Image.blend(im,Image.new('RGB',(W,H),target_color),ease((t-(sc[0]-.55))/.55))
  if elapsed+t>DURATION-.55:im=Image.blend(im,Image.new('RGB',(W,H),background(index)),ease((elapsed+t-(DURATION-.55))/.55))
  p.stdin.write(im.tobytes())
 elapsed+=sc[0]
p.stdin.close();assert p.wait()==0
probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(ROOT/'Booklat-demo-v3-57s.mp4')]))
assert float(probe['format']['duration'])<=60
v=next(s for s in probe['streams'] if s['codec_type']=='video');assert int(v['nb_frames'])==1710
(ROOT/'verification-v3.json').write_text(json.dumps({'duration_seconds':float(probe['format']['duration']),'frames':int(v['nb_frames']),'resolution':f"{v['width']}x{v['height']}",'fps':v['r_frame_rate'],'audio':'Original synthesized instrumental; no voiceover','mock':'Actual Booklat UI; synthetic recognition events; isolated demo database'},indent=2))
print('Verified',probe['format']['duration'],'seconds,',v['nb_frames'],'frames',flush=True)
