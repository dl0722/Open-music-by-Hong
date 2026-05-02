# ═════════════════════════════════════════════════════════════════════════════
#  OpenMusic v4.8 — 曜石玻璃潮流增强版
#  PySide6 + pygame + numpy + mutagen + Pillow
# ═════════════════════════════════════════════════════════════════════════════

import sys,os,math,random,time,hashlib,re,traceback,json
from pathlib import Path
from collections import deque
from PySide6.QtWidgets import *; from PySide6.QtCore import *; from PySide6.QtGui import *
import pygame,numpy as np,mutagen; from mutagen import File as MutagenFile
from mutagen.mp3 import MP3; from mutagen.flac import FLAC; from PIL import Image

pygame.mixer.pre_init(44100,-16,2,2048); pygame.init(); pygame.mixer.set_num_channels(8)
SE={'.mp3','.wav','.flac','.ogg','.aac','.m4a'}; SK={'.cache','__pycache__','_internal'}
BANDS=48; FPS=30

# ── PyInstaller 打包路径修正 ──
if getattr(sys,'frozen',False):
    SD=os.path.dirname(os.path.abspath(sys.executable))
    if '_MEI' in SD:
        SD=os.path.dirname(os.path.abspath(sys.argv[0]))
else:
    SD=os.path.dirname(os.path.abspath(__file__))
DESKTOP=os.path.join(os.path.expanduser("~"),"Desktop")

# ── 配色常量（曜石玻璃 + 电光青金 + 珊瑚点缀）──
C_BG="#101216"; C_SIDEBAR="#151922"; C_CONTENT="#1B2029"
C_DIVIDER="#2B3340"
C_ACCENT="#4DE1C1"; C_ACCENT_LIGHT="#8FE7FF"; C_PRESSED="#18A88F"
C_WARN="#FFB86B"; C_CORAL="#FF6F91"
C_TEXT1="#F4F7FB"; C_TEXT2="#B9C3D4"; C_TEXT3="#6F7B8D"
C_HOVER="#242B36"; C_SELECT_BG="#182B31"
C_SEARCH_BG="#121820"
STATE_FILE=os.path.join(SD,'.cache','openmusic_state.json')

# ── 全局阴影工具 ──
def add_shadow(widget,radius=8,dx=0,dy=4,color=QColor(0,0,0,80)):
    s=QGraphicsDropShadowEffect(widget)
    s.setBlurRadius(radius);s.setOffset(dx,dy);s.setColor(color)
    widget.setGraphicsEffect(s)
    
# ── 渐变背景widget（暖棕柔雾 + 磨砂噪点）──
class BgWidget(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
    def paintEvent(self,ev):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        w,h=self.width(),self.height()
        p.fillRect(0,0,w,h,QColor(C_BG))
        g=QRadialGradient(w*0.58,h*0.22,min(w,h)*0.85)
        g.setColorAt(0,QColor("#203644"));g.setColorAt(0.45,QColor("#151922"));g.setColorAt(1,QColor(C_BG))
        p.fillRect(0,0,w,h,QBrush(g))
        g2=QRadialGradient(w*0.18,h*0.82,min(w,h)*0.55)
        g2.setColorAt(0,QColor(255,111,145,34));g2.setColorAt(1,QColor(255,111,145,0))
        p.fillRect(0,0,w,h,QBrush(g2))
        g3=QRadialGradient(w*0.86,h*0.68,min(w,h)*0.5)
        g3.setColorAt(0,QColor(77,225,193,30));g3.setColorAt(1,QColor(77,225,193,0))
        p.fillRect(0,0,w,h,QBrush(g3))
        # 极淡噪点纹理
        for _ in range(50):
            x=random.randint(0,w);y=random.randint(0,h)
            c=random.choice([QColor(255,255,255,3),QColor(0,0,0,4)])
            p.fillRect(x,y,1,1,c)
        p.end()

def fmt(s):
    if s is None or s<0: return "0:00"
    return f"{int(s)//60}:{int(s)%60:02d}"

def album_color(name):
    h=hashlib.md5((name or '').encode()).hexdigest()
    r1=int(h[0:2],16)%100+140;g1=int(h[2:4],16)%80+90;b1=int(h[4:6],16)%60+50
    r2=int(h[6:8],16)%80+160;g2=int(h[8:10],16)%60+80;b2=int(h[10:12],16)%40+60
    return (r1,g1,b1),(r2,g2,b2)

class ColorMan:
    _inst=None
    def __new__(cls):
        if cls._inst is None:
            cls._inst=super().__new__(cls)
            cls._inst.p=(200,155,105);cls._inst.s=(160,120,80);cls._inst.a=(212,175,130)
        return cls._inst
    def from_cover(self,path):
        try:
            img=Image.open(path).convert('RGB').resize((64,64))
            px=np.array(img).reshape(-1,3)
            self.p=tuple(px[px.sum(axis=1).argmax()])
        except: pass

class Meta:
    @staticmethod
    def read(path):
        fn=Path(path).stem;nm=fn;ar="";al="";dur=0
        try:
            mf=MutagenFile(path)
            if mf:
                if hasattr(mf.info,'length'): dur=mf.info.length
                if hasattr(mf,'tags') and mf.tags:
                    tg={k.lower():v for k,v in mf.tags.items()}
                    def g(k): return str(tg[k][0] if isinstance(tg.get(k),list) else tg.get(k,''))
                    n=g('title');a=g('artist');l=g('album')
                    if n: nm=n
                    if a: ar=a
                    if l: al=l
        except: pass

        # ── 歌手识别 ──
        # 一级：ID3标签（上面已完成）
        # 二级：父文件夹名（用户按文件夹分歌手，最可靠）
        if not ar:
            parent=Path(path).parent.name
            if parent and parent not in ('Open Music',os.path.basename(SD)):
                ar=parent
        # 三级：文件名解析
        if not ar:
            if ' - ' in fn:
                # 格式 "歌名 - 歌手.mp3" → 后半段是歌手
                ps=fn.split(' - ',1)
                if len(ps)==2 and ps[1].strip():
                    ar=ps[1].strip()
            else:
                # 格式 "歌名-歌手.品质.mp3" → 去掉品质码后按最后一个"-"分割
                clean=re.sub(r'\.\d{3,}$','',fn)
                pos=clean.rfind('-')
                if pos>0:
                    candidate=clean[pos+1:].strip()
                    if candidate: ar=candidate
        # ── 歌名清理（无论歌手从哪来，都要清理文件名中的歌手部分）──
        if nm==fn or not nm:
            if ' - ' in fn:
                nm=fn.split(' - ',1)[0].strip()
            else:
                clean=re.sub(r'\.\d{3,}$','',fn)
                pos=clean.rfind('-')
                if pos>0: nm=clean[:pos].strip()
        # ID3标题有值时优先用
        try:
            mf=MutagenFile(path)
            if mf and hasattr(mf,'tags') and mf.tags:
                n=str(mf.tags.get('title',[''])[0] if isinstance(mf.tags.get('title'),list) else mf.tags.get('title',''))
                if n: nm=n
        except: pass
        return {'path':path,'name':nm,'artist':ar,'album':al,'dur':dur}
    @staticmethod
    def cover(path):
        try:
            mf=MutagenFile(path)
            if mf is None: return None
            data=None
            if isinstance(mf,MP3):
                for t in mf.tags.values():
                    if getattr(t,'FrameID','')=='APIC': data=t.data;break
            elif isinstance(mf,FLAC) and mf.pictures: data=mf.pictures[0].data
            if data is None: return None
            cache=os.path.join(SD,'.cache');os.makedirs(cache,exist_ok=True)
            cp=os.path.join(cache,hashlib.md5(path.encode()).hexdigest()+'.jpg')
            if not os.path.exists(cp):
                with open(cp,'wb') as f: f.write(data)
            return cp
        except: return None

# ── 音频 ──
class Audio(QObject):
    pos_changed=Signal(float);state_changed=Signal(int);track_ended=Signal()
    S,P,PA=0,1,2
    def __init__(self,parent=None):
        super().__init__(parent)
        self._sd=None;self._ch=None;self._path="";self._dur=0;self._vol=0.8;self._st=self.S
        self._ps=0;self._pe=0;self._speed=1.0;self._spec_frames=None;self._spec_step=0.05
        self._tm=QTimer(self);self._tm.setInterval(16)
        self._tm.timeout.connect(self._tick);self._history=deque(maxlen=50)
    @property
    def state(self): return self._st
    @property
    def dur(self): return self._dur
    def load(self,path):
        self.stop()
        try:
            mf=MutagenFile(path)
            self._dur=mf.info.length if mf and hasattr(mf.info,'length') else 0
            self._path=path;self._sd=True
            if path not in self._history: self._history.append(path)
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(self._vol)
            pygame.mixer.music.play()
            self._ps=time.time();self._pe=0
            self._st=self.P;self.state_changed.emit(self.P);self._tm.start()
            QTimer.singleShot(80,lambda p=path: self._prepare_spec(p) if self._path==p else None)
        except: self._st=self.S;self.state_changed.emit(self.S)
    def toggle(self):
        if self._st==self.P:
            pygame.mixer.music.pause();self._pe=self._pos()
            self._st=self.PA;self.state_changed.emit(self.PA)
        elif self._st==self.PA:
            pygame.mixer.music.unpause()
            self._ps=time.time()-(self._pe if self._pe>0 else 0);self._pe=0
            self._st=self.P;self.state_changed.emit(self.P)
    def stop(self):
        self._tm.stop()
        pygame.mixer.music.stop()
        self._sd=None;self._ch=None;self._st=self.S;self.state_changed.emit(self.S)
    def seek(self,r):
        if not self._sd or self._dur<=0: return
        tgt=r*self._dur
        ok=False
        try:
            pygame.mixer.music.play(start=max(0,tgt))
            ok=True
        except:
            try:
                pygame.mixer.music.rewind()
                pygame.mixer.music.set_pos(max(0,tgt))
                ok=True
            except: return
        if ok:
            self._ps=time.time()-tgt;self._pe=0;self._st=self.P;self.state_changed.emit(self.P)
    def set_vol(self,v):
        self._vol=max(0,min(1,v));pygame.mixer.music.set_volume(self._vol)
    def set_speed(self,s): self._speed=max(0.5,min(2.0,s))
    def _prepare_spec(self,path):
        self._spec_frames=None
        try:
            if os.path.exists(path) and os.path.getsize(path)>30*1024*1024:
                return
            snd=pygame.mixer.Sound(path)
            arr=pygame.sndarray.array(snd)
            if arr is None or arr.size==0: return
            if arr.ndim>1: arr=arr.mean(axis=1)
            arr=arr.astype(np.float32)
            mx=np.max(np.abs(arr))
            if mx>0: arr/=mx
            sr=pygame.mixer.get_init()[0] or 44100
            chunk=max(1024,int(sr*self._spec_step))
            hop=chunk
            frames=[]
            window=np.hanning(chunk)
            weights=np.linspace(1.12,0.55,BANDS)
            max_frames=3600
            for fi,start in enumerate(range(0,len(arr)-chunk,hop)):
                if fi>=max_frames: break
                seg=arr[start:start+chunk]*window
                rms=float(np.sqrt(np.mean(seg*seg)))
                fft=np.abs(np.fft.rfft(seg))
                if len(fft)<BANDS+1: continue
                edges=np.linspace(1,len(fft)-1,BANDS+1).astype(int)
                vals=[]
                for i in range(BANDS):
                    lo,hi=edges[i],max(edges[i]+1,edges[i+1])
                    vals.append(float(np.mean(fft[lo:hi])))
                vals=np.array(vals,dtype=np.float32)
                if vals.max()>0: vals/=vals.max()
                vals=np.power(np.clip(vals,0,1),0.62)
                beat=min(1.0,rms*2.45)
                vals=np.clip(vals*0.72+beat*0.58*weights,0,1)
                frames.append(vals)
            if frames:
                self._spec_frames=np.array(frames,dtype=np.float32)
        except:
            self._spec_frames=None
    def _pos(self):
        if self._st==self.P and self._sd: return min(self._pe+(time.time()-self._ps),self._dur)
        return self._pe
    def _tick(self):
        if self._st==self.P and self._sd:
            p=self._pos()
            if self._dur>0 and p>=self._dur-0.3:
                self._st=self.S;self.state_changed.emit(self.S);self.track_ended.emit();self._tm.stop()
            self.pos_changed.emit(p)
    def spec_data(self):
        if self._st!=self.P or not self._sd: return None
        if self._spec_frames is not None and len(self._spec_frames)>0:
            idx=int(self._pos()/self._spec_step)
            idx=max(0,min(len(self._spec_frames)-1,idx))
            return np.repeat(self._spec_frames[idx],2)
        t=time.time()
        d=np.zeros(BANDS*2)
        for i in range(len(d)):
            bm=max(0,1.0-i/len(d)*1.5);bt=math.sin(t*4.0)*0.3+0.5
            md=0.15*math.exp(-((i-len(d)*0.3)/(len(d)*0.1))**2)
            d[i]=bm*bt*0.6+md+random.uniform(0,0.1)
        return np.clip(d,0,1)
    def close(self): self._tm.stop();self.stop()

class SpecAna:
    def __init__(self):
        self.sm=np.zeros(BANDS);self.pk=np.zeros(BANDS);self.en=0
    def feed(self,d):
        if d is None: self.en*=0.9;self.sm*=0.95;return
        a=np.array(d[:BANDS*2:2] if len(d)>=BANDS*2 else np.zeros(BANDS))
        if len(a)<BANDS: a=np.pad(a,(0,BANDS-len(a)))
        a=np.power(np.clip(a[:BANDS],0,1),0.72)
        self.sm=self.sm*0.52+a*0.48
        m=self.sm>self.pk;self.pk[m]=self.sm[m];self.pk[~m]*=0.93
        self.en=float(np.mean(self.sm))

# ── 自绘播放按钮（带波纹扩散） ──
class PlayButton(QPushButton):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setFixedSize(34,34);self.setCursor(Qt.PointingHandCursor)
        self._playing=False;self._ripple_r=0;self._ripple_a=0;self._tip_text="播放"
        self._ripple_tm=QTimer(self);self._ripple_tm.timeout.connect(self._ripple_tick)
    def set_tip(self,t): self._tip_text=t
    def set_playing(self,p): self._playing=p;self.set_tip("暂停" if p else "播放");self.update()
    def enterEvent(self,ev):
        if self._tip_text:
            w=self.window()
            if w and hasattr(w,'_tip') and w._tip:
                w._tip.show_tip(self._tip_text,self)
    def leaveEvent(self,ev):
        w=self.window()
        if w and hasattr(w,'_tip') and w._tip:
            w._tip.hide_tip()
    def mouseReleaseEvent(self,ev):
        if ev.button()==Qt.LeftButton:
            self.clicked.emit();self._ripple_r=2;self._ripple_a=180;self._ripple_tm.start(16)
    def _ripple_tick(self):
        self._ripple_r+=2.5;self._ripple_a=max(0,self._ripple_a-8)
        if self._ripple_a<=0: self._ripple_tm.stop()
        self.update()
    def paintEvent(self,ev):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        r=16;cx,cy=self.width()/2,self.height()/2
        g=QRadialGradient(cx,cy,r)
        g.setColorAt(0,QColor(C_ACCENT_LIGHT));g.setColorAt(1,QColor(C_ACCENT))
        p.setBrush(QBrush(g));p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx,cy),r,r)
        if self._playing:
            pw=4;ph=10;gap=3
            p.setBrush(Qt.white);p.setPen(Qt.NoPen)
            p.drawRect(QRectF(cx-gap-pw,cy-ph/2,pw,ph))
            p.drawRect(QRectF(cx+gap,cy-ph/2,pw,ph))
        else:
            poly=QPolygonF([QPointF(cx-4,cy-6),QPointF(cx-4,cy+6),QPointF(cx+7,cy)])
            p.setBrush(Qt.white);p.setPen(Qt.NoPen);p.drawPolygon(poly)
        if self._ripple_a>0:
            p.setPen(QPen(QColor(C_ACCENT_LIGHT),2));p.setBrush(Qt.NoBrush)
            p.drawEllipse(QPointF(cx,cy),self._ripple_r,self._ripple_r)

# ── 拟态图标系统 ──
class NeumorphBtn(QPushButton):
    """Neumorphism 拟态风格按钮，代码自绘图标"""
    ICON_PREV=0;ICON_NEXT=1;ICON_PLAY=2;ICON_PAUSE=3
    ICON_VOLUME=4;ICON_EQ=5;ICON_SPEC=6;ICON_CLOCK=7;ICON_MINI=8

    def __init__(self,icon_id,size=26,parent=None):
        super().__init__(parent)
        self._icon=icon_id;self.setFixedSize(size,size)
        self.setCursor(Qt.PointingHandCursor);self._pressed=False
        self._active=False;self._hover=False;self._tip_text=""
        self._vol_level=80

    def set_active(self,a): self._active=a;self.update()
    def set_tip(self,t): self._tip_text=t

    def enterEvent(self,ev):
        self._hover=True;self.update()
        if self._tip_text:
            w=self.window()
            if w and hasattr(w,'_tip') and w._tip:
                w._tip.show_tip(self._tip_text,self)
    def leaveEvent(self,ev):
        self._hover=False;self.update()
        w=self.window()
        if w and hasattr(w,'_tip') and w._tip:
            w._tip.hide_tip()
    def mousePressEvent(self,ev): self._pressed=True;self.update();super().mousePressEvent(ev)
    def mouseReleaseEvent(self,ev): self._pressed=False;self.update();super().mouseReleaseEvent(ev)

    def paintEvent(self,ev):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        s=self.width();hs=s//2
        bg=QColor(24,30,40,225 if self._hover else 175)
        hl=QColor(143,231,255,36 if self._hover else 14)
        sd=QColor(0,0,0,55 if self._hover else 35)
        if self._pressed: hl,sd=sd,hl
        # 拟态阴影
        p.setPen(Qt.NoPen)
        p.setBrush(hl);p.drawEllipse(QPointF(hs,hs),hs-1,hs-1)
        p.setBrush(sd);p.drawEllipse(QPointF(hs,hs),hs-2,hs-2)
        p.setBrush(bg);p.drawEllipse(QPointF(hs,hs),hs,hs)

        # 图标颜色
        ic=QColor(C_ACCENT) if self._active else QColor(C_TEXT2)
        ci=ic.red(),ic.green(),ic.blue()

        # 绘制图标
        {self.ICON_PREV:self._prev,self.ICON_NEXT:self._next,
         self.ICON_VOLUME:self._vol,self.ICON_EQ:self._eq,
         self.ICON_SPEC:self._spec,self.ICON_CLOCK:self._clock,
         self.ICON_MINI:self._mini}[self._icon](p,hs,ci)

    def _prev(self,p,c,ci):
        """上一首"""
        sz=c*0.34;color=QColor(*ci,210)
        p.setBrush(color);p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(c-sz*1.15,c-sz*.65,2,sz*1.3),1,1)
        poly=QPolygonF([QPointF(c+sz*.55,c-sz*.75),QPointF(c-sz*.35,c),QPointF(c+sz*.55,c+sz*.75)])
        p.drawPolygon(poly)
    def _next(self,p,c,ci):
        """下一首"""
        sz=c*0.34;color=QColor(*ci,210)
        p.setBrush(color);p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(c+sz*1.0,c-sz*.65,2,sz*1.3),1,1)
        poly=QPolygonF([QPointF(c-sz*.55,c-sz*.75),QPointF(c+sz*.35,c),QPointF(c-sz*.55,c+sz*.75)])
        p.drawPolygon(poly)
    def _vol(self,p,c,ci):
        """扬声器—根据音量画声波条数"""
        sz=c*0.35
        # 喇叭体
        pts=[QPointF(c-sz*0.75,c-sz*.45),QPointF(c-sz*0.35,c-sz*.45),QPointF(c+sz*0.15,c-sz*.82),
             QPointF(c+sz*0.15,c+sz*.82),QPointF(c-sz*0.35,c+sz*.45),QPointF(c-sz*0.75,c+sz*.45)]
        p.setBrush(QColor(*ci,200));p.setPen(Qt.NoPen);p.drawPolygon(QPolygonF(pts))
        vl=getattr(self,'_vol_level',80)
        if vl==0:
            # 静音: 画X
            p.setPen(QPen(QColor(*ci,200),2))
            p.drawLine(int(c+sz*0.1-sz*0.15),int(c-sz*0.15),int(c+sz*0.1+sz*0.15),int(c+sz*0.15))
            p.drawLine(int(c+sz*0.1+sz*0.15),int(c-sz*0.15),int(c+sz*0.1-sz*0.15),int(c+sz*0.15))
        else:
            n=3 if vl>60 else (2 if vl>20 else 1)
            p.setPen(QPen(QColor(*ci,150),1.5))
            for i in range(n):
                p.drawArc(QRectF(c+sz*0.3-i*sz*0.2,c-sz*i*0.6,sz*i*0.6,sz*i*1.2),-60*16,120*16)
    def _eq(self,p,c,ci):
        """三条均衡器柱"""
        bw=c*0.08;gap=c*0.16
        hs=[c*0.2,c*0.5,c*0.35]
        p.setPen(Qt.NoPen)
        for i,h in enumerate(hs):
            x=c+c*0.2+i*(bw+gap)-c*0.3
            p.setBrush(QColor(*ci,200));p.drawRoundedRect(QRectF(x-bw/2,c-h,bw,h*2),bw/2,bw/2)
    def _spec(self,p,c,ci):
        """频谱图标"""
        n=4;bw=c*0.08;gap=c*0.13
        hs=[c*0.2,c*0.6,c*0.45,c*0.3]
        p.setPen(Qt.NoPen)
        for i,h in enumerate(hs):
            x=c-gap*1.5+i*(bw+gap)
            p.setBrush(QColor(*ci,200));p.drawRoundedRect(QRectF(x-bw/2,c-h,bw,h),bw/2,bw/2)
    def _clock(self,p,c,ci):
        """钟表"""
        r=c*0.35
        p.setPen(_icon_pen(QColor(*ci,200),1.5));p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(c,c),r,r)
        p.drawLine(QPointF(c,c),QPointF(c,c-r*0.6))
        p.drawLine(QPointF(c,c),QPointF(c+r*0.5,c+r*0.15))
    def _mini(self,p,c,ci):
        """窗口还原"""
        sz=c*0.3;gap=3
        p.setPen(_icon_pen(QColor(*ci,200),1.5));p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(c-sz*0.7,c-sz*0.7,sz*1.4,sz*1.4),3,3)
        p.drawRoundedRect(QRectF(c-sz*0.7+gap,c-sz*0.7+gap,sz*1.4-2,sz*1.4-2),3,3)

class SimpleIconBtn(QPushButton):
    """简单线性图标按钮，hover变主色"""
    def __init__(self,draw_fn,tip="",size=22,parent=None):
        super().__init__(parent)
        self.setFixedSize(size,size);self.setCursor(Qt.PointingHandCursor)
        self._draw=draw_fn;self._hover=False;self._tip=tip
    def enterEvent(self,ev):
        self._hover=True;self.update()
        if self._tip:
            w=self.window()
            if w and hasattr(w,'_tip') and w._tip:
                w._tip.show_tip(self._tip,self)
    def leaveEvent(self,ev):
        self._hover=False;self.update()
        w=self.window()
        if w and hasattr(w,'_tip') and w._tip:
            w._tip.hide_tip()
    def paintEvent(self,ev):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        s=self.width();c=s//2
        col=QColor(C_ACCENT) if self._hover else QColor(C_TEXT2)
        if self._hover:
            g=QRadialGradient(c,c,s*0.55)
            g.setColorAt(0,QColor(77,225,193,55));g.setColorAt(1,QColor(77,225,193,0))
            p.setPen(Qt.NoPen);p.setBrush(QBrush(g));p.drawEllipse(QPointF(c,c),s*0.48,s*0.48)
        self._draw(p,s,c,col)
        p.end()

def _icon_pen(color,w=1.65):
    pen=QPen(color,w)
    pen.setCapStyle(Qt.RoundCap);pen.setJoinStyle(Qt.RoundJoin)
    return pen

def _loop_icon(p,s,c,color):
    p.setPen(_icon_pen(color));p.setBrush(Qt.NoBrush)
    r=QRectF(c-s*.27,c-s*.25,s*.54,s*.50)
    p.drawArc(r,35*16,285*16)
    p.drawLine(QPointF(c+s*.20,c-s*.18),QPointF(c+s*.27,c-s*.25))
    p.drawLine(QPointF(c+s*.20,c-s*.18),QPointF(c+s*.11,c-s*.21))
def _lyric_icon(p,s,c,color):
    p.setPen(_icon_pen(color));p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(c-s*.23,c-s*.25,s*.46,s*.50),4,4)
    for i,wid in enumerate([.22,.30,.18]):
        y=c-s*.10+i*s*.12
        p.drawLine(QPointF(c-s*.13,y),QPointF(c-s*.13+s*wid,y))
def _fullscreen_icon(p,s,c,color):
    p.setPen(_icon_pen(color));p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(c-s*.24,c-s*.24,s*.48,s*.48),3,3)
    p.drawLine(QPointF(c-s*.08,c-s*.24),QPointF(c+s*.08,c-s*.24))
    p.drawLine(QPointF(c-s*.08,c+s*.24),QPointF(c+s*.08,c+s*.24))
def _fav_icon(p,s,c,color):
    """收藏心形空框"""
    p.setPen(_icon_pen(color));p.setBrush(Qt.NoBrush)
    path=QPainterPath()
    path.moveTo(c,c+s*0.15)
    path.cubicTo(c-s*0.35,c-s*0.1,c-s*0.15,c-s*0.4,c,c-s*0.15)
    path.cubicTo(c+s*0.15,c-s*0.4,c+s*0.35,c-s*0.1,c,c+s*0.15)
    p.drawPath(path)

# ── 灵动岛 Toast ──
class ToastW(QFrame):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"ToastW{{background:rgba(95,66,44,240);border:1px solid {C_DIVIDER};border-radius:16px;}}")
        self.hide()
        lo=QHBoxLayout(self);lo.setContentsMargins(18,10,18,10)
        self._lb=QLabel("");self._lb.setStyleSheet(f"color:{C_TEXT1};font-size:12px;background:transparent;")
        lo.addWidget(self._lb)
        self._anim=QPropertyAnimation(self,b"pos",self)
        self._anim.setDuration(400);self._anim.setEasingCurve(QEasingCurve.OutBack)
        self._hide_timer=QTimer(self);self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._slide_out)
        # 动画状态标志 + 连接标志（彻底消除RuntimeWarning）
        self._anim_state=None
        self._anim_connected=False
    def show_msg(self,msg):
        pw=self.parent().width() if self.parent() else 600
        max_w=min(400,pw-40)
        # 单行，过长用省略号，固定高度保证文字完整不截断
        fm=QFontMetrics(QFont("Microsoft YaHei UI",12))
        display=fm.elidedText(msg,Qt.ElideRight,max_w-36)
        self._lb.setFont(QFont("Microsoft YaHei UI",12));self._lb.setText(display)
        self.setFixedWidth(max_w);self.setFixedHeight(38)
        x=(pw-max_w)//2;ty=self.parent().height()-100
        self.move(x,ty+40);self.raise_();self.show()
        # 只在有连接时断开
        if self._anim_connected:
            try: self._anim.finished.disconnect()
            except: pass
            self._anim_connected=False
        self._anim.setStartValue(QPoint(x,ty+40))
        self._anim.setEndValue(QPoint(x,ty))
        self._anim_state='show_msg'
        self._anim.start();self._hide_timer.start(2000)
    def _slide_out(self):
        if self._anim_state=='slide_out': return  # 已在滑出
        self._anim_state='slide_out'
        self._anim.setEasingCurve(QEasingCurve.InBack)
        self._anim.setStartValue(self.pos())
        self._anim.setEndValue(QPoint(self.x(),self.parent().height()+20))
        self._anim.finished.connect(lambda: self.hide())
        self._anim_connected=True
        self._anim.start()
        self._anim.setEasingCurve(QEasingCurve.InBack)
        self._anim.setStartValue(self.pos())
        self._anim.setEndValue(QPoint(self.x(),self.parent().height()+20))
        self._anim.finished.connect(lambda: self.hide())
        self._anim.start()

# ── 悬浮提示 Tip ──
class TipW(QFrame):
    """鼠标悬浮时显示的功能说明浮窗，移开自动消失"""
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.hide()
        lo=QHBoxLayout(self);lo.setContentsMargins(12,6,12,6)
        self._lb=QLabel("");self._lb.setStyleSheet(f"color:{C_TEXT1};font-size:11px;background:transparent;")
        lo.addWidget(self._lb)
        self.setStyleSheet(f"TipW{{background:{C_CONTENT};border:1px solid {C_ACCENT}40;border-radius:8px;}}")
    def show_tip(self,text,widget):
        self._lb.setText(text);self.adjustSize()
        # 定位到控件上方居中
        tl=widget.mapToGlobal(QPoint(0,0))
        x=tl.x()+(widget.width()-self.width())//2
        y=tl.y()-self.height()-8
        # 确保不超出屏幕
        sg=QGuiApplication.primaryScreen().availableGeometry()
        if x<sg.x(): x=sg.x()+4
        if x+self.width()>sg.x()+sg.width(): x=sg.x()+sg.width()-self.width()-4
        if y<sg.y(): y=tl.y()+widget.height()+8  # 超出则显示在下方
        self.move(x,y);self.show();self.raise_()
    def hide_tip(self):
        self.hide()

# ── 弹性进度条 ──
class SnapSlider(QSlider):
    def __init__(self,parent=None):
        super().__init__(Qt.Horizontal,parent)
        self.setRange(0,1000)
        self.setFixedHeight(30)
        self._wave=[0.15+0.75*(math.sin(i*0.73)+1)/2 for i in range(72)]
        self._anim=QPropertyAnimation(self,b"value",self)
        self._anim.setDuration(300);self._anim.setEasingCurve(QEasingCurve.OutBack)
    def _value_from_x(self,x):
        if self.width()<=0: return self.value()
        return max(0,min(1000,int(x/self.width()*1000)))
    def mouseReleaseEvent(self,ev):
        super().mouseReleaseEvent(ev)
        self.sliderReleased.emit()
    def mousePressEvent(self,ev):
        if ev.button()==Qt.LeftButton:
            self._anim.stop()
            self.setValue(self._value_from_x(ev.position().x()))
            self.sliderPressed.emit()
            ev.accept()
            return
        super().mousePressEvent(ev)
    def mouseMoveEvent(self,ev):
        if ev.buttons()&Qt.LeftButton:
            self.setValue(self._value_from_x(ev.position().x()))
            ev.accept()
            return
        super().mouseMoveEvent(ev)
    def paintEvent(self,ev):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        w,h=self.width(),self.height();cy=h/2
        if w<=4: p.end();return
        ratio=self.value()/max(1,self.maximum())
        n=len(self._wave);gap=max(2,w/(n*1.35));bar_w=max(2,gap*0.55)
        start=(w-(n-1)*gap)/2
        for i,a in enumerate(self._wave):
            x=start+i*gap
            if x<0 or x>w: continue
            live=x/w<=ratio
            amp=(3+a*h*0.34)*(1+0.18*math.sin(time.time()*4+i*0.4))
            c=QColor(C_ACCENT if live else C_DIVIDER)
            alpha=230 if live else 120
            if live and i>n*ratio-5: alpha=255
            p.setBrush(QColor(c.red(),c.green(),c.blue(),alpha));p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRectF(x-bar_w/2,cy-amp/2,bar_w,amp),bar_w/2,bar_w/2)
        hx=max(16,min(w-16,w*ratio))
        glow=QRadialGradient(hx,cy,13)
        glow.setColorAt(0,QColor(143,231,255,155));glow.setColorAt(0.45,QColor(77,225,193,85));glow.setColorAt(1,QColor(143,231,255,0))
        p.setBrush(QBrush(glow));p.setPen(Qt.NoPen);p.drawEllipse(QPointF(hx,cy),13,13)
        p.setBrush(QColor(C_ACCENT));p.drawEllipse(QPointF(hx,cy),4.2,4.2)
        p.end()

# ── 频谱 ──
class SpecWidget(QWidget):
    mode_changed=Signal(int)
    MODES=["Bars","Ring","Wave","3D Bars","Particles"]
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setMinimumHeight(80);self._ana=SpecAna();self._mode=0
        self._phase=0;self._particles=[]
        self._tm=QTimer(self);self._tm.timeout.connect(lambda: self.update())
        self._tm.start(1000//FPS)
    def next_mode(self):
        self._mode=(self._mode+1)%len(self.MODES);self.mode_changed.emit(self._mode);self.update()
    def set_mode(self,m): self._mode=m%len(self.MODES);self.update()
    def paintEvent(self,ev):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        w,h=self.width(),self.height()
        if w<10 or h<10: p.end();return
        self._phase+=0.045
        d=self._ana.sm;n=len(d)
        if n==0: p.end();return
        {0:self._bars,1:self._ring,2:self._wave,3:self._d3,4:self._part}[self._mode](p,w,h,d)
        p.end()
    def _sample(self,d,x):
        if len(d)==0: return 0
        idx=max(0,min(len(d)-1,int(x*(len(d)-1))))
        return float(d[idx])
    def _bars(self,p,w,h,d):
        n=len(d);bw=max(3,int((w-n)/(n*1.55)));yb=h*0.68
        gap=max(2,int(bw*0.46))
        total_w=n*bw+(n-1)*gap;sx=(w-total_w)/2+bw/2
        c1=QColor(C_ACCENT)
        energy=max(0.02,min(0.55,self._ana.en))
        for i in range(n):
            raw=max(0.0,min(1.0,float(d[i])))
            v=math.pow(raw,0.72)
            bh=max(2.0,min(h*0.72,(v*0.82+energy*0.18)*yb));t=i/n
            x=sx+i*(bw+gap)
            alpha=max(55,min(235,int(72+132*(1-abs(t-0.5)*2)+v*38)))
            c=QColor(c1.red(),c1.green(),c1.blue(),alpha)
            p.setBrush(c);p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRectF(x-bw/2,(h-bh)/2,bw,bh),2,2)
            if v>0.72:
                p.setBrush(QColor(C_ACCENT_LIGHT).lighter(105));p.setPen(Qt.NoPen)
                p.drawRoundedRect(QRectF(x-bw/2,(h-bh)/2,bw,2.0),1,1)
    def _ring(self,p,w,h,d):
        n=len(d);cx,cy=w//2,h//2;r=min(w,h)//3;c1,c2=QColor(C_ACCENT),QColor(C_ACCENT_LIGHT)
        p.setPen(QPen(QColor(77,225,193,34),1));p.drawEllipse(QPointF(cx,cy),r*.72,r*.72)
        for i in range(n):
            ang=i/n*6.2832-1.5708;v=float(d[i]);t=i/n
            ri=int(c1.red()+(c2.red()-c1.red())*t);gi=int(c1.green()+(c2.green()-c1.green())*t);bi=int(c1.blue()+(c2.blue()-c1.blue())*t)
            x1=cx+math.cos(ang)*r*0.7;y1=cy+math.sin(ang)*r*0.7
            x2=cx+math.cos(ang)*(r+v*r*0.8);y2=cy+math.sin(ang)*(r+v*r*0.8)
            p.setPen(QPen(QColor(ri,gi,bi,120),max(1,w//n//3),Qt.SolidLine,Qt.RoundCap))
            p.drawLine(QPointF(x1,y1),QPointF(x2,y2))
    def _wave(self,p,w,h,d):
        c=QColor(C_ACCENT);n=len(d);path=QPainterPath()
        path.moveTo(0,h/2)
        for i in range(n):
            x=i*(w/n);v=float(d[i])
            path.lineTo(x,h/2-v*h*0.36)
        path.lineTo(w,h/2);path.closeSubpath()
        p.fillPath(path,QColor(c.red(),c.green(),c.blue(),42))
        p.setPen(QPen(QColor(c.red(),c.green(),c.blue(),150),1.4,Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin))
        p.drawPath(path)
    def _d3(self,p,w,h,d):
        c=QColor(C_ACCENT);n=len(d);bw=max(3,w//n//2)
        for i in range(n):
            v=float(d[i]);bh=v*h*0.6
            if bh<2: continue
            p.fillRect(QRectF(i*(w//n),h-bh,bw,bh),QColor(c.red(),c.green(),c.blue(),180))
            p.fillRect(QRectF(i*(w//n)+bw,h-bh-5,5,bh+5),QColor(c.red()//2,c.green()//2,c.blue()//2,100))
    def _part(self,p,w,h,d):
        e=self._ana.en;c=QColor(C_ACCENT);cx,cy=w//2,h//2
        if not hasattr(self,'_ps') or not self._ps:
            self._ps=[{'x':cx+math.cos(random.uniform(0,6.28))*random.uniform(0,w*0.3),
                'y':cy+math.sin(random.uniform(0,6.28))*random.uniform(0,h*0.3),
                'vx':random.uniform(-1,1),'vy':random.uniform(-1,1),
                's':random.uniform(1,3),'l':random.uniform(0.3,1),'d':random.uniform(0.008,0.02)} for _ in range(25)]
        for pt in self._ps[:]:
            pt['x']+=pt['vx'];pt['y']+=pt['vy'];pt['l']-=pt['d']
            if pt['l']<=0:
                if len(self._ps)>15: self._ps.remove(pt);continue
            a=int(pt['l']*120);sz=pt['s']*pt['l']
            p.setBrush(QColor(c.red(),c.green(),c.blue(),a));p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(pt['x'],pt['y']),sz,sz)

# ── 专辑卡片 ──
class AlbumGrid(QScrollArea):
    album_clicked=Signal(str)
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True);self.setFrameShape(QFrame.NoFrame)
        self.setStyleSheet(f"AlbumGrid{{background:transparent;border:none;}}"
            f"QScrollBar:vertical{{width:4px;background:{C_DIVIDER};border-radius:2px;}}"
            f"QScrollBar::handle:vertical{{background:{C_TEXT3};border-radius:2px;}}")
        self._c=QWidget();self._c.setStyleSheet("background:transparent;")
        self._g=QGridLayout(self._c);self._g.setSpacing(10)
        self._g.setContentsMargins(16,16,16,16);self.setWidget(self._c)
    def set_albums(self,albums):
        while self._g.count():
            it=self._g.takeAt(0)
            if it and it.widget(): it.widget().deleteLater()
        cols=max(2,min(5,self.width()//150))
        for i,(name,artist,cover,cnt) in enumerate(albums):
            card=AlbumCard(name,artist,cover,cnt)
            card.clicked.connect(lambda n=name: self.album_clicked.emit(n))
            self._g.addWidget(card,i//cols,i%cols)

class AlbumCard(QFrame):
    clicked=Signal()
    def __init__(self,name,artist,cover,cnt):
        super().__init__()
        self.setFixedSize(130,160);self.setCursor(Qt.PointingHandCursor)
        c1,c2=album_color(name)
        cs=f"border-radius:8px;background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 rgb{c1},stop:1 rgb{c2});"
        self.setStyleSheet(f"AlbumCard{{background:{C_CONTENT};border-radius:10px;border:1px solid {C_DIVIDER};}}"
            f"AlbumCard:hover{{background:{C_HOVER};border-color:{C_ACCENT};}}")
        lo=QVBoxLayout(self);lo.setContentsMargins(6,6,6,4);lo.setSpacing(3)
        self._cv=QLabel();self._cv.setFixedSize(116,116);self._cv.setAlignment(Qt.AlignCenter)
        if cover and os.path.exists(cover):
            px=QPixmap(cover).scaled(116,116,Qt.KeepAspectRatio,Qt.SmoothTransformation)
            self._cv.setPixmap(px);self._cv.setStyleSheet("border-radius:8px;")
        else:
            self._cv.setText("♩");self._cv.setStyleSheet(cs+f"color:{C_TEXT3};font-size:36px;")
        lo.addWidget(self._cv,0,Qt.AlignCenter)
        nm=name if len(name)<12 else name[:11]+"…"
        nl=QLabel(nm);nl.setStyleSheet(f"color:{C_TEXT1};font-size:10px;font-weight:bold;")
        nl.setAlignment(Qt.AlignCenter);lo.addWidget(nl)
        cl=QLabel(f"{cnt}首 · {artist}" if artist else f"{cnt}首")
        cl.setStyleSheet(f"color:{C_TEXT3};font-size:9px;");cl.setAlignment(Qt.AlignCenter);lo.addWidget(cl)
    def mouseReleaseEvent(self,ev): self.clicked.emit()

# ── 底部栏 ──
class BottomBar(QFrame):
    pp_sig=Signal();prv_sig=Signal();nxt_sig=Signal()
    seek_sig=Signal(float);vol_sig=Signal(float);spec_sig=Signal()
    sleep_sig=Signal();eq_sig=Signal()
    mode_sig=Signal(int,str);speed_sig=Signal(float)
    def __init__(self,parent=None):
        super().__init__(parent)
        self._seeking=False
        self.setFixedHeight(76)
        self.setStyleSheet(f"BottomBar{{background:rgba(16,18,22,235);border-top:1px solid rgba(77,225,193,70);}}")
        lo=QHBoxLayout(self);lo.setContentsMargins(14,8,14,8);lo.setSpacing(0)
        
        # ── 左侧：封面 + 歌曲信息 ──
        left_w=QWidget();left_w.setFixedWidth(240)
        ll=QHBoxLayout(left_w);ll.setContentsMargins(0,0,0,0);ll.setSpacing(8)
        self._cv=QLabel();self._cv.setFixedSize(40,40)
        self._cv.setStyleSheet(f"background:{C_DIVIDER};border-radius:8px;border:1px solid rgba(77,225,193,45);")
        self._cv.setAlignment(Qt.AlignCenter)
        ll.addWidget(self._cv)
        info_v=QVBoxLayout();info_v.setSpacing(0)
        self._ti=QLabel("未播放");self._ti.setStyleSheet(f"color:{C_TEXT1};font-size:12px;font-weight:bold;background:transparent;")
        self._ti_full="";self._ti_offset=0
        self._ti_tm=QTimer(self);self._ti_tm.timeout.connect(self._ti_scroll);self._ti_tm.setInterval(300)
        self._ar=QLabel("");self._ar.setStyleSheet(f"color:{C_TEXT2};font-size:10px;background:transparent;")
        info_v.addWidget(self._ti);info_v.addWidget(self._ar)
        ll.addLayout(info_v,stretch=1);lo.addWidget(left_w)
        
        lo.addStretch()
        # ── 中间：控制区 ──
        ctrl_w=QWidget()
        cvl=QVBoxLayout(ctrl_w);cvl.setContentsMargins(0,0,0,0);cvl.setSpacing(4)
        # 按钮行
        btn_h=QHBoxLayout();btn_h.setContentsMargins(0,0,0,0);btn_h.setSpacing(6)
        btn_h.addStretch()
        self._prv=NeumorphBtn(NeumorphBtn.ICON_PREV,22)
        self._prv.set_tip("上一首")
        btn_h.addWidget(self._prv)
        self._pp=PlayButton()
        btn_h.addWidget(self._pp)
        self._nxt=NeumorphBtn(NeumorphBtn.ICON_NEXT,22)
        self._nxt.set_tip("下一首")
        btn_h.addWidget(self._nxt)
        btn_h.addStretch()
        cvl.addLayout(btn_h)
        # 进度行
        prog_h=QHBoxLayout();prog_h.setContentsMargins(0,0,0,0);prog_h.setSpacing(6)
        self._tc=QLabel("0:00");self._tc.setStyleSheet(f"color:{C_TEXT2};font-size:9px;min-width:28px;")
        self._tc.setAlignment(Qt.AlignRight|Qt.AlignVCenter);prog_h.addWidget(self._tc)
        self._pb=SnapSlider();self._pb.setFixedWidth(300)
        self._pb.setStyleSheet("background:transparent;")
        self._pb.sliderPressed.connect(lambda: setattr(self,'_seeking',True))
        self._pb.sliderReleased.connect(self._release_seek)
        prog_h.addSpacing(8);prog_h.addWidget(self._pb);prog_h.addSpacing(8)
        self._tt=QLabel("0:00");self._tt.setStyleSheet(f"color:{C_TEXT2};font-size:9px;min-width:28px;");prog_h.addWidget(self._tt)
        # 倍速标签（放在进度条右侧）
        self._spd_btn=QPushButton("1×");self._spd_btn.setFixedSize(22,16)
        self._spd_btn.setStyleSheet(f"QPushButton{{background:transparent;color:{C_TEXT2};border-radius:8px;font-size:7px;border:1px solid {C_DIVIDER};margin:0;padding:0;}}"
            f"QPushButton:hover{{color:{C_ACCENT};border-color:{C_ACCENT};}}")
        self._spd_btn.clicked.connect(self._cycle_speed)
        prog_h.addWidget(self._spd_btn)
        cvl.addLayout(prog_h)
        lo.addWidget(ctrl_w)
        
        lo.addStretch()
        # ── 右侧：功能图标 + 音量 ──
        right_w=QFrame();right_w.setFixedSize(296,40)
        right_w.setStyleSheet(
            "QFrame{background:rgba(15,20,27,165);border:1px solid rgba(77,225,193,36);"
            "border-radius:20px;}"
        )
        rl=QHBoxLayout(right_w);rl.setContentsMargins(9,0,9,0);rl.setSpacing(7)
        self._loop_btn=SimpleIconBtn(_loop_icon,"循环模式",22)
        self._loop_btn.clicked.connect(lambda: self._cycle_mode());rl.addWidget(self._loop_btn)
        self._eq_btn=NeumorphBtn(NeumorphBtn.ICON_EQ,22)
        self._eq_btn.set_tip("均衡器")
        self._eq_btn.clicked.connect(self.eq_sig.emit);rl.addWidget(self._eq_btn)
        self._sp_btn=NeumorphBtn(NeumorphBtn.ICON_SPEC,22)
        self._sp_btn.set_tip("频谱模式")
        self._sp_btn.clicked.connect(self.spec_sig.emit);rl.addWidget(self._sp_btn)
        self._ly_btn=SimpleIconBtn(_lyric_icon,"歌词",22)
        self._ly_btn.clicked.connect(lambda: self.parent()._toggle_lyrics() if self.parent() and hasattr(self.parent(),'_toggle_lyrics') else self._toast_msg("歌词"));rl.addWidget(self._ly_btn)
        self._mt=NeumorphBtn(NeumorphBtn.ICON_VOLUME,22)
        self._mt.set_tip("静音")
        self._mt.clicked.connect(lambda: self._vs.setValue(0 if self._vs.value()>0 else 80));rl.addWidget(self._mt)
        self._vs=QSlider(Qt.Horizontal);self._vs.setRange(0,100);self._vs.setValue(80);self._vs.setFixedWidth(58)
        self._vs.setStyleSheet(
            f"QSlider{{background:transparent;border:none;}}"
            f"QSlider::groove:horizontal{{background:rgba(111,123,141,80);border-radius:2px;height:4px}}"
            f"QSlider::handle:horizontal{{background:{C_ACCENT};border-radius:4px;width:8px;height:8px;margin:-2px 0}}"
            f"QSlider::sub-page:horizontal{{background:{C_ACCENT};border-radius:2px}}")
        self._vs.valueChanged.connect(lambda v: self.vol_sig.emit(v/100.0))
        rl.addWidget(self._vs)
        self._slp_btn=NeumorphBtn(NeumorphBtn.ICON_CLOCK,22)
        self._slp_btn.set_tip("睡眠定时")
        self._slp_btn.clicked.connect(self.sleep_sig.emit);rl.addWidget(self._slp_btn)
        lo.addWidget(right_w)
        
        # 信号
        self._pp.clicked.connect(self.pp_sig.emit)
        self._prv.clicked.connect(self.prv_sig.emit)
        self._nxt.clicked.connect(self.nxt_sig.emit)
        self._speed_idx=0;self._speeds=[1.0,1.5,2.0,0.5]
    def _cycle_speed(self):
        self._speed_idx=(self._speed_idx+1)%4
        self._spd_btn.setText(f"{self._speeds[self._speed_idx]}×")
        self.speed_sig.emit(self._speeds[self._speed_idx])
    def _release_seek(self):
        self._seeking=False
        self.seek_sig.emit(self._pb.value()/1000.0)
    def _cycle_mode(self):
        modes=["顺序播放","列表循环","单曲循环","随机漫游"]
        self._mode_idx=getattr(self,'_mode_idx',-1)
        self._mode_idx=(self._mode_idx+1)%len(modes)
        self._loop_btn.setToolTip(modes[self._mode_idx])
        self.mode_sig.emit(self._mode_idx,modes[self._mode_idx])
        # 尝试通知父窗口切换模式
        if hasattr(self,'parent') and self.parent():
            mw=self.parent()
            while mw and not hasattr(mw,'_toast'):
                mw=mw.parent() if hasattr(mw,'parent') else None
            if mw and hasattr(mw,'_toast'):
                mw._toast.show_msg(f"播放模式：{modes[self._mode_idx]}")
    def set_mode(self,idx):
        modes=["顺序播放","列表循环","单曲循环","随机漫游"]
        self._mode_idx=max(0,min(idx,len(modes)-1))
        self._loop_btn.setToolTip(modes[self._mode_idx])
        self.mode_sig.emit(self._mode_idx,modes[self._mode_idx])
    def _toast_msg(self,msg):
        if hasattr(self,'parent') and self.parent():
            mw=self.parent()
            while mw and not hasattr(mw,'_toast'):
                mw=mw.parent() if hasattr(mw,'parent') else None
            if mw and hasattr(mw,'_toast'):
                mw._toast.show_msg(msg)
    def get_speed(self): return self._speeds[self._speed_idx]
    def _ti_scroll(self):
        if not self._ti_full: return
        self._ti_offset=(self._ti_offset+1)%(len(self._ti_full)+10)
        if self._ti_offset>len(self._ti_full): self._ti.setText(self._ti_full[:16])
        else: self._ti.setText(self._ti_full[self._ti_offset:self._ti_offset+16])
    def update_play(self,p): self._pp.set_playing(p)
    def update_pos(self,pos,dur):
        self._tc.setText(fmt(pos));self._tt.setText(fmt(dur))
        if dur>0 and not self._seeking:
            self._pb.blockSignals(True);self._pb.setValue(int(pos/dur*1000));self._pb.blockSignals(False)
    def update_song(self,ti,ar,cv=None):
        self._ti_full=ti or "未播放";self._ti_offset=0;self._ti.setText(self._ti_full[:16])
        if len(self._ti_full)>16: self._ti_tm.start()
        else: self._ti_tm.stop()
        self._ar.setText(ar or "")
        if cv and os.path.exists(cv):
            px=QPixmap(cv).scaled(40,40,Qt.KeepAspectRatio,Qt.SmoothTransformation)
            self._cv.setPixmap(px)
        else:
            self._cv.setText("♩");self._cv.setStyleSheet(f"color:{C_TEXT3};font-size:18px;background:{C_DIVIDER};border-radius:8px;")
    def set_cover(self,cv):
        if cv and os.path.exists(cv):
            px=QPixmap(cv).scaled(40,40,Qt.KeepAspectRatio,Qt.SmoothTransformation)
            self._cv.setPixmap(px)

# ── 左侧面板 ──
def _make_icon(w,draw_fn):
    """生成 16x16 QIcon"""
    px=QPixmap(w,w);px.fill(Qt.transparent)
    p=QPainter(px);p.setRenderHint(QPainter.Antialiasing)
    draw_fn(p,w)
    p.end()
    return QIcon(px)

def _icon_list(p,w):
    c=w/2
    p.setPen(_icon_pen(QColor(C_TEXT2),1.6));p.setBrush(Qt.NoBrush)
    for i in range(3):
        y=c-4+i*4
        p.drawLine(QPointF(c-3,y),QPointF(c+5,y))
        p.drawEllipse(QPointF(c-5,y),.8,.8)
def _icon_user(p,w):
    c=w/2;r=w*0.22
    p.setPen(_icon_pen(QColor(C_TEXT2),1.6));p.setBrush(Qt.NoBrush)
    p.drawEllipse(QPointF(c,c-r*0.8),r,r)
    p.drawArc(QRectF(c-r,c+r*0.3,r*2,r*1.2),0,-180*16)
def _icon_disc(p,w):
    c=w/2;r=w*0.3
    p.setPen(_icon_pen(QColor(C_TEXT2),1.6));p.setBrush(Qt.NoBrush)
    p.drawEllipse(QPointF(c,c),r,r)
    p.setPen(_icon_pen(QColor(C_TEXT2),1.1));p.drawEllipse(QPointF(c,c),r*0.3,r*0.3)
def _icon_shuffle(p,w):
    c=w/2;r=w*0.25
    p.setPen(_icon_pen(QColor(C_TEXT2),1.6));p.setBrush(Qt.NoBrush)
    p.drawLine(QPointF(c-r,c-r),QPointF(c+r*.15,c-r))
    p.drawLine(QPointF(c+r*.15,c-r),QPointF(c+r,c+r*.55))
    p.drawLine(QPointF(c-r,c+r),QPointF(c+r*.15,c+r))
    p.drawLine(QPointF(c+r*.15,c+r),QPointF(c+r,c-r*.55))
    p.drawLine(QPointF(c+r*.75,c-r*.8),QPointF(c+r,c-r*.55))
    p.drawLine(QPointF(c+r*.75,c+r*.8),QPointF(c+r,c+r*.55))
def _icon_clock(p,w):
    c=w/2;r=w*0.3
    p.setPen(_icon_pen(QColor(C_TEXT2),1.6));p.setBrush(Qt.NoBrush)
    p.drawEllipse(QPointF(c,c),r,r)
    p.drawLine(QPointF(c,c),QPointF(c,c-r*0.6))
    p.drawLine(QPointF(c,c),QPointF(c+r*0.4,c))
def _icon_heart(p,w):
    c=w/2
    p.setPen(_icon_pen(QColor(C_TEXT2),1.6));p.setBrush(Qt.NoBrush)
    path=QPainterPath()
    path.moveTo(c,c+w*0.15)
    path.cubicTo(c-w*0.4,c-w*0.1,c-w*0.2,c-w*0.45,c,c-w*0.15)
    path.cubicTo(c+w*0.2,c-w*0.45,c+w*0.4,c-w*0.1,c,c+w*0.15)
    p.drawPath(path)
def _icon_plus(p,w):
    c=w/2
    p.setPen(_icon_pen(QColor(C_TEXT2),1.8))
    p.drawLine(QPointF(c,c-w*0.25),QPointF(c,c+w*0.25))
    p.drawLine(QPointF(c-w*0.25,c),QPointF(c+w*0.25,c))

class SidebarItemDelegate(QStyledItemDelegate):
    def paint(self,painter,opt,idx):
        painter.save();painter.setRenderHint(QPainter.Antialiasing)
        r=opt.rect;selected=opt.state&QStyle.State_Selected;hover=opt.state&QStyle.State_MouseOver
        txt=idx.data(Qt.DisplayRole);icon_id=idx.data(Qt.UserRole+1)
        painter.fillRect(r,QColor(C_SIDEBAR))
        if selected:
            painter.fillRect(QRectF(r.x(),r.y()+2,2,r.height()-4),QColor(C_ACCENT))
            painter.fillRect(r.adjusted(2,0,0,0),QColor(24,43,49,230))
        elif hover: painter.fillRect(r,QColor(C_HOVER))
        tc=QColor(C_ACCENT) if selected else (QColor(C_TEXT1) if hover else QColor(C_TEXT2))
        # 绘制图标
        if icon_id is not None:
            iw=16;ix=r.x()+10;iy=r.y()+(r.height()-iw)//2
            px=QPixmap(iw,iw);px.fill(Qt.transparent)
            ip=QPainter(px);ip.setRenderHint(QPainter.Antialiasing)
            ip.setPen(_icon_pen(tc,1.6));ip.setBrush(Qt.NoBrush)
            draw_fns=[_icon_list,_icon_user,_icon_disc,_icon_shuffle,_icon_clock,_icon_heart,_icon_plus]
            if 0<=icon_id<len(draw_fns): draw_fns[icon_id](ip,iw)
            ip.end()
            painter.drawPixmap(ix,iy,px)
            txt_x=ix+iw+8
        else: txt_x=r.x()+14
        # 文字
        painter.setPen(tc);painter.setFont(opt.font)
        painter.drawText(txt_x,r.y(),r.width()-txt_x-10,r.height(),Qt.AlignVCenter|Qt.AlignLeft,txt)
        painter.restore()
    def sizeHint(self,opt,idx): return QSize(180,32)

class LeftPanel(QFrame):
    cat_sig=Signal(str)
    NAV_ITEMS=[("全部音乐",0),("歌手",1),("专辑",2),("随机播放",3),("播放历史",4)]
    BOTTOM_ITEMS=[("我的收藏",5),("最近添加",6)]
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setFixedWidth(180)
        self.setStyleSheet(f"background:transparent;")
        lo=QVBoxLayout(self);lo.setContentsMargins(0,0,0,0);lo.setSpacing(0)
        # 顶部品牌
        brand=QWidget();brand.setFixedHeight(58)
        bl=QHBoxLayout(brand);bl.setContentsMargins(12,4,12,4)
        nl=QLabel("♩");nl.setStyleSheet(f"color:{C_ACCENT};font-size:18px;font-weight:bold;background:transparent;")
        bl.addWidget(nl)
        brand_txt=QVBoxLayout();brand_txt.setContentsMargins(0,0,0,0);brand_txt.setSpacing(0)
        nm=QLabel("OpenMusic");nm.setStyleSheet(f"color:{C_TEXT1};font-size:13px;font-weight:bold;background:transparent;")
        by=QLabel("By Hong");by.setStyleSheet(f"color:{C_ACCENT};font-size:8px;font-weight:bold;background:transparent;letter-spacing:0px;")
        brand_txt.addWidget(nm);brand_txt.addWidget(by)
        bl.addLayout(brand_txt);bl.addStretch()
        lo.addWidget(brand)
        lo.addSpacing(4)
        # 导航列表
        self._list=QListWidget();self._list.setFrameShape(QFrame.NoFrame)
        self._list.setStyleSheet(
            f"QListWidget{{background:transparent;border:none;outline:none;}}"
            f"QListWidget::item{{background:transparent;color:transparent;border:none;}}")
        self._list.setItemDelegate(SidebarItemDelegate(self._list))
        for txt,iid in self.NAV_ITEMS:
            it=QListWidgetItem();it.setText(txt);it.setData(Qt.UserRole+1,iid)
            self._list.addItem(it)
        self._list.itemClicked.connect(lambda it: self.cat_sig.emit(it.text()))
        self._list.setCurrentRow(0)
        lo.addWidget(self._list,stretch=1)
        # 底部导航项
        bottom_w=QWidget()
        bw_lo=QVBoxLayout(bottom_w);bw_lo.setContentsMargins(0,4,0,8);bw_lo.setSpacing(0)
        sep=QFrame();sep.setFixedHeight(1);sep.setStyleSheet(f"background:{C_DIVIDER};margin:0 10px;")
        bw_lo.addWidget(sep);bw_lo.addSpacing(4)
        self._bottom_list=QListWidget();self._bottom_list.setFrameShape(QFrame.NoFrame)
        self._bottom_list.setStyleSheet(
            f"QListWidget{{background:transparent;border:none;outline:none;}}"
            f"QListWidget::item{{background:transparent;color:transparent;border:none;}}")
        self._bottom_list.setItemDelegate(SidebarItemDelegate(self._bottom_list))
        for txt,iid in self.BOTTOM_ITEMS:
            it=QListWidgetItem();it.setText(txt);it.setData(Qt.UserRole+1,iid)
            self._bottom_list.addItem(it)
        self._bottom_list.itemClicked.connect(lambda it: self._on_bottom(it.text()))
        bw_lo.addWidget(self._bottom_list)
        lo.addWidget(bottom_w)
    def _on_bottom(self,txt):
        if txt=="我的收藏": self.parent().parent()._on_cat("收藏")
        elif txt=="最近添加": self.parent().parent()._on_cat("最近添加")

# ── 均衡器 ──
EQ_B=[31,62,125,250,500,1000,2000,4000,8000,16000]
EQ_P={"Normal":[0,0,0,0,0,0,0,0,0,0],"Pop":[3,2,1,0,-1,0,1,2,3,2],
    "Rock":[4,3,2,1,0,-1,0,1,3,4],"Bass":[5,4,3,2,1,0,-1,-1,0,0],"Vocal":[-1,-1,0,1,2,3,3,2,1,0]}
class EqPanel(QFrame):
    def __init__(self,parent=None):
        super().__init__(parent)
        self._sl=[];self._bs=False
        self.setStyleSheet(f"background:{C_CONTENT};border:1px solid {C_DIVIDER};border-radius:8px;")
        lo=QVBoxLayout(self);lo.setContentsMargins(10,4,10,4);lo.setSpacing(2)
        hl=QHBoxLayout();t2=QLabel("均衡器");t2.setStyleSheet(f"color:{C_TEXT1};font-size:11px;font-weight:bold;")
        hl.addWidget(t2);hl.addStretch();lo.addLayout(hl)
        sl=QHBoxLayout();sl.setSpacing(2)
        for f in EQ_B:
            vl=QVBoxLayout();vl.setSpacing(1)
            fl=QLabel(f"{f}Hz" if f<1000 else f"{f//1000}KHz");fl.setAlignment(Qt.AlignCenter)
            fl.setStyleSheet(f"color:{C_TEXT3};font-size:7px;");vl.addWidget(fl)
            sd=QSlider(Qt.Vertical);sd.setRange(-12,12);sd.setValue(0);sd.setFixedSize(14,50)
            sd.setStyleSheet(
                f"QSlider::groove:vertical{{background:{C_DIVIDER};border-radius:1px;width:2px;margin:0 5px}}"
                f"QSlider::handle:vertical{{background:{C_ACCENT};border-radius:3px;height:6px;width:6px;margin:-2px 0}}"
                f"QSlider::sub-page:vertical{{background:{C_ACCENT};border-radius:1px;width:2px}}")
            vl.addWidget(sd,0,Qt.AlignCenter);sl.addLayout(vl);self._sl.append(sd)
        lo.addLayout(sl)
        bl=QHBoxLayout();bl.setSpacing(4)
        for n in list(EQ_P.keys()):
            b=QPushButton(n);b.setFixedHeight(18)
            b.setStyleSheet(f"QPushButton{{background:{C_SIDEBAR};color:{C_ACCENT};border-radius:3px;font-size:8px;padding:1px 5px;border:1px solid {C_DIVIDER};}}"
                f"QPushButton:hover{{background:{C_HOVER};border-color:{C_ACCENT};}}")
            b.clicked.connect(lambda checked,nm=n: self._ap(nm))
            bl.addWidget(b)
        lo.addLayout(bl)
    def _ap(self,nm):
        if nm not in EQ_P: return
        gs=EQ_P[nm];self._bs=True
        for i,g in enumerate(gs): self._sl[i].setValue(g)
        self._bs=False

# ═════════════════════════════════════════════════════════════════════════════
#  场景覆盖层（光晕+粒子+爆裂）
# ═════════════════════════════════════════════════════════════════════════════
class SceneOverlay(QWidget):
    """透明覆盖层：氛围光晕 + 粒子星云 + 爆裂粒子"""
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._glow_color=QColor(77,225,193,35);self._glow_energy=0
        self._flow=0
        self._bps=[{'x':random.uniform(0,100),'y':random.uniform(0,100),
            'vx':random.uniform(-0.15,0.15),'vy':random.uniform(-0.15,0.15),
            's':random.uniform(1,2.5),'a':random.uniform(15,45),'px':0,'py':0} for _ in range(25)]
        self._bursts=[];self._ripples=[];self._shimmer_x=-50
        self._tm=QTimer(self);self._tm.timeout.connect(self._tick);self._tm.start(33)
    def set_glow(self,color,energy=0):
        self._glow_color=QColor(color[0],color[1],color[2],35)
        self._glow_energy=energy
    def burst(self,x,y):
        # 将坐标转换到当前widget坐标系
        for _ in range(12):
            ang=random.uniform(0,6.28);spd=random.uniform(1,3.5)
            self._bursts.append({'x':x,'y':y,'vx':math.cos(ang)*spd,'vy':math.sin(ang)*spd,
                's':random.uniform(1.5,3),'a':120,'life':1.0,'decay':random.uniform(0.025,0.045),
                'cr':200+random.randint(0,55),'cg':150+random.randint(0,40),'cb':90+random.randint(0,40)})
    def click_ripple(self,x,y):
        self._ripples.append({'x':x,'y':y,'r':1.5,'a':70,'life':1.0,'decay':0.08})
    def _tick(self):
        up=False
        for bp in self._bursts[:]:
            bp['x']+=bp['vx'];bp['y']+=bp['vy'];bp['life']-=bp['decay']
            bp['a']=int(bp['life']*200)
            if bp['life']<=0: self._bursts.remove(bp);continue
            up=True
        for rp in self._ripples[:]:
            rp['r']+=1.1;rp['a']=int(rp['life']*70);rp['life']-=rp['decay']
            if rp['life']<=0: self._ripples.remove(rp);continue;up=True
        for p in self._bps:
            p['px'],p['py']=p['x'],p['y']
            p['x']+=p['vx'];p['y']+=p['vy']
            if p['x']<0 or p['x']>100: p['vx']*=-1
            if p['y']<0 or p['y']>100: p['vy']*=-1
        self._shimmer_x=(self._shimmer_x+1.5)%(self.width()+100)
        self._flow+=0.012+self._glow_energy*0.015
        self.update()
    def paintEvent(self,ev):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        w,h=self.width(),self.height()
        if w<10 or h<10: p.end();return
        pulse=1.0+self._glow_energy*0.3
        for i,(cx,cy,rr) in enumerate([(w*0.3,h*0.35,w*0.5),(w*0.7,h*0.65,w*0.4)]):
            cx+=math.sin(self._flow+i)*w*.04;cy+=math.cos(self._flow*.8+i)*h*.04
            ga=QRadialGradient(cx,cy,rr*pulse);c=self._glow_color
            ga.setColorAt(0,QColor(c.red(),c.green(),c.blue(),max(14,34+int(self._glow_energy*34))))
            ga.setColorAt(1,QColor(c.red(),c.green(),c.blue(),0))
            p.setBrush(QBrush(ga));p.setPen(Qt.NoPen);p.drawEllipse(QPointF(cx,cy),rr*pulse,rr*pulse)
        for pt in self._bps:
            x=pt['x']/100*w;y=pt['y']/100*h;px=pt['px']/100*w;py=pt['py']/100*h
            for t2 in range(4):
                tt=t2/4;lx=px+(x-px)*tt;ly=py+(y-py)*tt
                a=int(pt['a']*0.3*(1-tt))
                p.setBrush(QColor(143,231,255,a));p.setPen(Qt.NoPen);p.drawEllipse(QPointF(lx,ly),pt['s']*tt,pt['s']*tt)
        for bp in self._bursts:
            p.setBrush(QColor(bp['cr'],bp['cg'],bp['cb'],bp['a']))
            p.setPen(Qt.NoPen);p.drawEllipse(QPointF(bp['x'],bp['y']),bp['s']*bp['life'],bp['s']*bp['life'])
        for rp in self._ripples:
            p.setPen(QPen(QColor(77,225,193,rp['a']),1.0));p.setBrush(Qt.NoBrush)
            p.drawEllipse(QPointF(rp['x'],rp['y']),rp['r'],rp['r'])
        py2=h-45
        g2=QLinearGradient(self._shimmer_x-40,py2,self._shimmer_x+40,py2)
        g2.setColorAt(0,QColor(77,225,193,0));g2.setColorAt(0.5,QColor(77,225,193,16));g2.setColorAt(1,QColor(77,225,193,0))
        p.fillRect(QRectF(0,py2,w,4),QBrush(g2))
        p.end()

# ═════════════════════════════════════════════════════════════════════════════
#  主窗口
# ═════════════════════════════════════════════════════════════════════════════

# ── 歌曲列表 delegate（分组+播放行高亮）──
class SongItemDelegate(QStyledItemDelegate):
    def __init__(self,parent=None):
        super().__init__(parent)
        self._playing_path=""
        self._hover_row=-1
    def set_playing(self,path): self._playing_path=path
    def paint(self,painter,opt,idx):
        painter.save();painter.setRenderHint(QPainter.Antialiasing)
        r=opt.rect;w=self.parent().width() if self.parent() else r.width()
        item_type=idx.data(Qt.UserRole+2)
        is_header=item_type=="header"
        is_playing=item_type=="song" and idx.data(Qt.UserRole)==self._playing_path
        hover=opt.state&QStyle.State_MouseOver
        
        if is_header:
            # 分组标题
            painter.fillRect(r,QColor(C_CONTENT))
            painter.setPen(QColor(C_TEXT2))
            painter.setFont(QFont("Microsoft YaHei UI",9))
            txt=idx.data(Qt.DisplayRole)
            painter.drawText(r.adjusted(14,0,0,0),Qt.AlignVCenter|Qt.AlignLeft,txt)
        else:
            # 歌曲行
            bg=QColor(C_CONTENT)
            if is_playing:
                g=QLinearGradient(r.x(),r.y(),r.x()+200,r.y())
                breath=18+int((math.sin(time.time()*3)+1)*18)
                g.setColorAt(0,QColor(77,225,193,36+breath));g.setColorAt(0.55,QColor(77,225,193,16));g.setColorAt(1,QColor(77,225,193,0))
                painter.fillRect(r,QBrush(g))
                painter.setBrush(QColor(77,225,193,140));painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(QRectF(r.x()+4,r.y()+8,3,r.height()-16),1.5,1.5)
            elif hover:
                painter.fillRect(r,QColor(C_HOVER))
                shine=QLinearGradient(r.x(),r.y(),r.right(),r.y())
                shine.setColorAt(0,QColor(77,225,193,0));shine.setColorAt(.18,QColor(77,225,193,26));shine.setColorAt(.42,QColor(143,231,255,14));shine.setColorAt(1,QColor(77,225,193,0))
                painter.fillRect(r,QBrush(shine))
            else:
                painter.fillRect(r,bg)
            # 分割线
            painter.setPen(QPen(QColor(43,51,64,140),1))
            RIGHT_PAD=28
            painter.drawLine(r.x()+10,r.bottom(),r.right()-RIGHT_PAD,r.bottom())
            # 列宽定义（固定，不依赖 parent().width()）
            DUR_W=52; AR_W=100; GAP=8
            # 从右往左计算各列 x 坐标
            dur_x=r.right()-RIGHT_PAD-DUR_W
            ar_x=dur_x-AR_W-GAP
            nm_max=ar_x-GAP-(r.x()+10+24)-GAP  # 歌名最大宽度
            txt_x=r.x()+14 if hover and not is_playing else r.x()+10
            # 封面
            cov_path=idx.data(Qt.UserRole+3) if is_playing else ""
            if is_playing and cov_path and os.path.exists(cov_path):
                px=QPixmap(cov_path).scaled(20,20,Qt.KeepAspectRatio,Qt.SmoothTransformation)
                painter.drawPixmap(r.x()+8,r.y()+8,20,20,px)
                txt_x=r.x()+34
                nm_max=ar_x-GAP-txt_x-GAP
            if is_playing:
                # 播放指示：3根跳动柱
                bi=getattr(self.parent(),'_play_bar_idx',0) if self.parent() else 0
                bar_h=[3,6,4,7,2,8,5]
                for ib in range(3):
                    bh=bar_h[(bi+ib)%len(bar_h)]
                    painter.setBrush(QColor(C_ACCENT));painter.setPen(Qt.NoPen)
                    painter.drawRoundedRect(txt_x+ib*5,r.y()+(r.height()-bh)//2,3,bh,1,1)
                txt_x+=20;nm_max-=20
            # 歌名
            nm=idx.data(Qt.DisplayRole)
            painter.setPen(QColor(C_ACCENT) if is_playing else QColor(C_TEXT1))
            f=QFont("Microsoft YaHei UI",10);f.setBold(is_playing)
            painter.setFont(f)
            nm_elided=QFontMetrics(f).elidedText(nm,Qt.ElideRight,max(40,nm_max))
            painter.drawText(txt_x,r.y(),max(40,nm_max),r.height(),Qt.AlignVCenter,nm_elided)
            # 歌手
            ar=idx.data(Qt.UserRole+4) or ""
            painter.setPen(QColor(C_TEXT3))
            painter.setFont(QFont("Microsoft YaHei UI",8))
            ar_elided=QFontMetrics(QFont("Microsoft YaHei UI",8)).elidedText(ar,Qt.ElideRight,AR_W)
            painter.drawText(ar_x,r.y(),AR_W,r.height(),Qt.AlignVCenter,ar_elided)
            # 时长
            dur=idx.data(Qt.UserRole+5)
            if dur is not None:
                painter.setPen(QColor(C_TEXT3))
                painter.setFont(QFont("Microsoft YaHei UI",8))
                painter.drawText(dur_x,r.y(),DUR_W,r.height(),Qt.AlignVCenter|Qt.AlignRight,dur)
            # hover图标（右侧，悬停时显示，不与时长重叠）
            if hover and not is_playing:
                ic=QColor(C_TEXT2)
                painter.setPen(QPen(ic,1.5));painter.setBrush(Qt.NoBrush)
                bx=r.right()-RIGHT_PAD-36
                for ii in range(3):
                    cx=bx+ii*12;cy=r.y()+r.height()//2
                    if ii==0:
                        # 心形
                        path=QPainterPath()
                        path.moveTo(cx,cy+2)
                        path.cubicTo(cx-4,cy-2,cx-3,cy-5,cx,cy-2)
                        path.cubicTo(cx+3,cy-5,cx+4,cy-2,cx,cy+2)
                        painter.drawPath(path)
                    elif ii==1: painter.drawLine(cx-3,cy,cx+3,cy);painter.drawLine(cx,cy-3,cx,cy+3)
                    else: painter.drawEllipse(QPointF(cx,cy-1),2,2)
        painter.restore()
    def sizeHint(self,opt,idx):
        if idx.data(Qt.UserRole+2)=="header": return QSize(0,24)
        return QSize(0,36)

class StatsStrip(QFrame):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setFixedHeight(58)
        self.setStyleSheet("StatsStrip{background:transparent;border:none;}")
        lo=QHBoxLayout(self);lo.setContentsMargins(18,8,18,8);lo.setSpacing(0)
        island=QFrame();island.setFixedHeight(42)
        island.setStyleSheet(
            "QFrame{background:rgba(15,20,27,178);border:1px solid rgba(77,225,193,48);"
            "border-radius:21px;}"
        )
        il=QHBoxLayout(island);il.setContentsMargins(14,4,14,4);il.setSpacing(0)
        self._labs=[];self._title_labs=[]
        titles=["曲库","歌手","收藏","总时长","已听"]
        for idx,title in enumerate(titles):
            box=QFrame();box.setFixedSize(96 if idx<3 else 118,32)
            box.setStyleSheet(
                "QFrame{background:transparent;border:none;border-radius:16px;}"
                "QFrame:hover{background:rgba(77,225,193,22);}"
            )
            bl=QVBoxLayout(box);bl.setContentsMargins(6,1,6,1);bl.setSpacing(0)
            v=QLabel("0");v.setAlignment(Qt.AlignCenter)
            v.setStyleSheet(f"color:{C_TEXT1};font-size:15px;font-weight:bold;background:transparent;")
            t=QLabel(title);t.setAlignment(Qt.AlignCenter)
            t.setStyleSheet(f"color:{C_TEXT3};font-size:9px;background:transparent;")
            bl.addWidget(v);bl.addWidget(t)
            il.addWidget(box);self._labs.append(v);self._title_labs.append(t)
            if idx<len(titles)-1:
                sep=QFrame();sep.setFixedSize(1,20);sep.setStyleSheet("background:rgba(143,231,255,24);border:none;")
                il.addWidget(sep)
        lo.addWidget(island,0,Qt.AlignLeft|Qt.AlignVCenter)
        lo.addStretch()
    def update_stats(self,tracks,favs,listened=0):
        artists=len({t.get('artist') or '未知歌手' for t in tracks})
        dur=sum(t.get('dur') or 0 for t in tracks)
        def nice(sec,with_seconds=False):
            h=int(sec//3600);m=int((sec%3600)//60)
            if with_seconds and h==0:
                s=int(sec%60)
                return f"{m}m {s}s" if m else f"{s}s"
            return f"{h}h {m}m" if h else f"{m}m"
        vals=[str(len(tracks)),str(artists),str(len(favs)),nice(dur),nice(listened,True)]
        for lb,val in zip(self._labs,vals): lb.setText(val)

class LyricsPanel(QFrame):
    def __init__(self,parent=None):
        super().__init__(parent)
        self._lines=[];self._idx=-1
        self.setFixedHeight(86)
        self.setStyleSheet(f"LyricsPanel{{background:rgba(18,24,32,190);border-top:1px solid rgba(255,111,145,45);border-bottom:1px solid rgba(77,225,193,35);}}")
        lo=QVBoxLayout(self);lo.setContentsMargins(16,8,16,8);lo.setSpacing(2)
        self._cur=QLabel("暂无歌词");self._cur.setAlignment(Qt.AlignCenter)
        self._cur.setStyleSheet(f"color:{C_TEXT1};font-size:14px;font-weight:bold;background:transparent;")
        self._next=QLabel("");self._next.setAlignment(Qt.AlignCenter)
        self._next.setStyleSheet(f"color:{C_TEXT3};font-size:10px;background:transparent;")
        lo.addWidget(self._cur);lo.addWidget(self._next)
    def load_for(self,path):
        self._lines=[];self._idx=-1
        base=os.path.splitext(path)[0]
        for lp in [base+".lrc",base+".txt"]:
            if os.path.exists(lp):
                try:
                    raw=Path(lp).read_text(encoding="utf-8",errors="ignore").splitlines()
                    for ln in raw:
                        ms=re.findall(r'\[(\d+):(\d+(?:\.\d+)?)\]',ln)
                        text=re.sub(r'\[[^\]]+\]','',ln).strip()
                        for mm,ss in ms:
                            if text: self._lines.append((int(mm)*60+float(ss),text))
                    if not self._lines and raw:
                        self._lines=[(i*4,line.strip()) for i,line in enumerate(raw) if line.strip()]
                    break
                except: pass
        self._lines.sort(key=lambda x:x[0])
        self.update_pos(0)
    def update_pos(self,pos):
        if not self._lines:
            self._cur.setText("暂无歌词");self._next.setText("把同名 .lrc 放在歌曲旁边即可显示")
            return
        idx=0
        for i,(t,_) in enumerate(self._lines):
            if t<=pos: idx=i
            else: break
        if idx!=self._idx:
            self._idx=idx
            self._cur.setText(self._lines[idx][1])
            self._next.setText(self._lines[idx+1][1] if idx+1<len(self._lines) else "")

class FocusPanel(QFrame):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setFixedHeight(84)
        self.setStyleSheet(f"FocusPanel{{background:rgba(18,24,32,130);border-top:1px solid rgba(77,225,193,28);border-bottom:1px solid rgba(77,225,193,38);}}")
        lo=QHBoxLayout(self);lo.setContentsMargins(18,8,18,8);lo.setSpacing(14)
        self._cover=QLabel();self._cover.setFixedSize(58,58);self._cover.setAlignment(Qt.AlignCenter)
        self._cover.setStyleSheet(f"background:{C_DIVIDER};border-radius:10px;border:1px solid rgba(77,225,193,55);color:{C_TEXT3};font-size:22px;")
        lo.addWidget(self._cover)
        txt=QVBoxLayout();txt.setSpacing(2)
        self._kicker=QLabel("NOW PLAYING");self._kicker.setStyleSheet(f"color:{C_ACCENT};font-size:8px;font-weight:bold;background:transparent;")
        self._title=QLabel("未播放");self._title.setStyleSheet(f"color:{C_TEXT1};font-size:15px;font-weight:bold;background:transparent;")
        self._artist=QLabel("");self._artist.setStyleSheet(f"color:{C_TEXT2};font-size:10px;background:transparent;")
        txt.addWidget(self._kicker);txt.addWidget(self._title);txt.addWidget(self._artist);lo.addLayout(txt,stretch=1)
        self._mode=QLabel("Bars");self._mode.setAlignment(Qt.AlignCenter)
        self._mode.setStyleSheet(f"color:{C_TEXT2};font-size:9px;padding:4px 10px;border:1px solid rgba(77,225,193,55);border-radius:9px;background:rgba(16,18,22,130);")
        lo.addWidget(self._mode)
        self._fx=QGraphicsOpacityEffect(self);self.setGraphicsEffect(self._fx);self._fx.setOpacity(0.88)
        self._anim=QPropertyAnimation(self._fx,b"opacity",self);self._anim.setDuration(220);self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.set_idle()
    def _fade_in(self):
        self._anim.stop();self._fx.setOpacity(0.55)
        self._anim.setStartValue(0.55);self._anim.setEndValue(1.0);self._anim.start()
    def set_idle(self):
        self._kicker.setText("OPEN MUSIC")
        self._title.setText("选择一首歌开始播放")
        self._artist.setText("双击歌曲，音乐会从这里流动起来")
        self._cover.setPixmap(QPixmap());self._cover.setText("♪")
        self._cover.setStyleSheet(f"background:{C_DIVIDER};border-radius:10px;border:1px solid rgba(77,225,193,38);color:{C_TEXT3};font-size:22px;")
    def update_song(self,title,artist,cover=None):
        self._kicker.setText("NOW PLAYING")
        self._title.setText(title or "未播放");self._artist.setText(artist or "")
        if cover and os.path.exists(cover):
            self._cover.setPixmap(QPixmap(cover).scaled(58,58,Qt.KeepAspectRatioByExpanding,Qt.SmoothTransformation))
            self._cover.setStyleSheet("border-radius:10px;border:1px solid rgba(77,225,193,65);")
        else:
            self._cover.setPixmap(QPixmap());self._cover.setText("♪")
            self._cover.setStyleSheet(f"background:{C_DIVIDER};border-radius:10px;border:1px solid rgba(77,225,193,55);color:{C_TEXT3};font-size:22px;")
        self._fade_in()
    def set_mode_name(self,name):
        self._mode.setText(name)
        self._fade_in()
class MainW(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OpenMusic");self.setMinimumSize(960,680);self.resize(1100,720)
        self.setAcceptDrops(True);self.setStyleSheet(f"MainW{{background:{C_BG};}}")
        self._audio=Audio(self);self._lib=[];self._track_path="";self._idx=-1
        self._sleep_timer=None;self._current_cover="";self._fav_set=set()
        self._sort_mode=0;self._sort_asc=True  # 0=歌名 1=歌手 2=时长
        self._play_mode=1;self._listened_seconds=0;self._last_listen_tick=None
        self._load_state()

        c=QWidget();self.setCentralWidget(c)
        ml=QVBoxLayout(c);ml.setContentsMargins(0,0,0,0);ml.setSpacing(0)
        
        # 渐变背景层
        self._bg=bg_w=BgWidget(c);bg_w.lower()

        # 顶部栏（精简：仅 Mini 按钮 + 页面名）
        tb=QFrame();tb.setFixedHeight(36)
        tb.setStyleSheet(f"background:transparent;border-bottom:1px solid {C_DIVIDER};")
        hl=QHBoxLayout(tb);hl.setContentsMargins(12,0,12,0)
        hl.addWidget(QLabel(""));hl.addStretch()
        self._page_lb=QLabel("全部音乐");self._page_lb.setStyleSheet(f"color:{C_TEXT2};font-size:11px;background:transparent;")
        hl.addWidget(self._page_lb)
        self._mini_btn=NeumorphBtn(NeumorphBtn.ICON_MINI,22)
        self._mini_btn.set_tip("迷你模式")
        self._mini_btn.clicked.connect(self._toggle_mini)
        hl.addWidget(self._mini_btn);ml.addWidget(tb)

        # 内容区
        mid=QHBoxLayout();mid.setContentsMargins(0,0,0,0);mid.setSpacing(0)
        self._lp=LeftPanel();mid.addWidget(self._lp)
        self._stack=QStackedWidget();self._stack.setStyleSheet("background:transparent;")

        # ── 主内容页 ──
        p0=QWidget();p0.setAttribute(Qt.WA_TranslucentBackground)
        p0l=QVBoxLayout(p0);p0l.setContentsMargins(0,0,0,0);p0l.setSpacing(0)
        
        # 页面标题
        self._pg=QLabel("全部音乐");self._pg.setFixedHeight(30)
        self._pg.setStyleSheet(f"color:{C_TEXT1};font-size:13px;font-weight:bold;padding:0 14px;background:transparent;")
        p0l.addWidget(self._pg)
        self._stats=StatsStrip();p0l.addWidget(self._stats)

        self._focus=FocusPanel();p0l.addWidget(self._focus)

        # ═══ 迷你播放信息模块 ═══
        self._mini_info=QWidget();self._mini_info.setFixedHeight(50)
        self._mini_info.setStyleSheet(f"background:transparent;")
        mil=QHBoxLayout(self._mini_info);mil.setContentsMargins(14,4,14,0);mil.setSpacing(10)
        # 左侧封面
        self._micv=QLabel();self._micv.setFixedSize(32,32)
        self._micv.setStyleSheet(f"background:{C_DIVIDER};border-radius:8px;border:1px solid rgba(77,225,193,45);")
        self._micv.setAlignment(Qt.AlignCenter)
        mil.addWidget(self._micv)
        # 歌名+歌手
        mi_v=QVBoxLayout();mi_v.setSpacing(0)
        self._miti=QLabel("");self._miti.setStyleSheet(f"color:{C_TEXT1};font-size:11px;font-weight:bold;background:transparent;")
        self._miar=QLabel("");self._miar.setStyleSheet(f"color:{C_TEXT2};font-size:9px;background:transparent;")
        mi_v.addWidget(self._miti);mi_v.addWidget(self._miar)
        mil.addLayout(mi_v,stretch=1)
        # 右侧图标
        self._fav_btn=SimpleIconBtn(_fav_icon,"收藏",20);self._fav_btn.clicked.connect(self._toggle_fav);mil.addWidget(self._fav_btn)
        self._ly_mini_btn=SimpleIconBtn(_lyric_icon,"歌词",20);self._ly_mini_btn.clicked.connect(self._toggle_lyrics);mil.addWidget(self._ly_mini_btn)
        self._mod_btn=SimpleIconBtn(_loop_icon,"播放模式",20);self._mod_btn.clicked.connect(lambda: self._bb._cycle_mode());mil.addWidget(self._mod_btn)
        self._mini_info.hide()
        p0l.addWidget(self._mini_info)

        self._lyrics=LyricsPanel();self._lyrics.hide();p0l.addWidget(self._lyrics)

        # ═══ 搜索栏 ═══
        sch_w=QWidget();sch_w.setFixedHeight(42)
        sch_w.setStyleSheet("background:transparent;")
        sch_lo=QHBoxLayout(sch_w);sch_lo.setContentsMargins(14,4,14,6);sch_lo.setSpacing(0)
        search_island=QFrame();search_island.setFixedHeight(32)
        search_island.setStyleSheet(
            "QFrame{background:rgba(15,20,27,150);border:1px solid rgba(77,225,193,42);"
            "border-radius:16px;}"
            "QFrame:hover{border-color:rgba(77,225,193,95);background:rgba(18,24,32,178);}"
        )
        sil=QHBoxLayout(search_island);sil.setContentsMargins(14,0,10,0);sil.setSpacing(8)
        # 搜索图标
        self._sch_icon=QLabel("⌕");self._sch_icon.setFixedSize(18,24)
        self._sch_icon.setAlignment(Qt.AlignCenter)
        self._sch_icon.setStyleSheet(f"color:{C_TEXT3};font-size:14px;background:transparent;border:none;")
        sil.addWidget(self._sch_icon)
        # 搜索框
        self._sch=QLineEdit()
        self._sch.setPlaceholderText("搜索歌曲、歌手...");self._sch.setFixedHeight(26)
        self._sch.setStyleSheet(
            f"QLineEdit{{background:transparent;color:{C_TEXT1};border:none;padding:2px 2px;font-size:11px;}}"
            f"QLineEdit:focus{{color:{C_TEXT1};}}")
        self._sch.textChanged.connect(self._filter);sil.addWidget(self._sch,stretch=1)
        # 右侧排序+视图图标
        self._sort_btn=SimpleIconBtn(_fullscreen_icon,"排序",18)
        self._sort_btn.clicked.connect(self._on_sort);sil.addWidget(self._sort_btn)
        self._view_btn=SimpleIconBtn(_loop_icon,"列表视图",18);sil.addWidget(self._view_btn)
        sch_lo.addWidget(search_island,stretch=1)
        p0l.addWidget(sch_w)

        # ═══ 频谱 ═══
        self._title_stack=QStackedWidget();self._title_stack.setFixedHeight(18)
        self._title_lb0=QLabel("");self._title_lb0.setAlignment(Qt.AlignCenter)
        self._title_lb0.setStyleSheet(f"color:{C_TEXT2};font-size:9px;background:transparent;")
        self._title_lb1=QLabel("");self._title_lb1.setAlignment(Qt.AlignCenter)
        self._title_lb1.setStyleSheet(f"color:{C_TEXT2};font-size:9px;background:transparent;")
        self._title_stack.addWidget(self._title_lb0);self._title_stack.addWidget(self._title_lb1)
        p0l.addWidget(self._title_stack)
        
        # 频谱（宽度通过外边距缩进对齐列表，高度缩短）
        sw_margin=QWidget();sw_margin.setFixedHeight(50)
        swl=QVBoxLayout(sw_margin);swl.setContentsMargins(14,0,14,0);swl.setSpacing(0)
        self._sw=SpecWidget();self._sw.setMinimumHeight(40);self._sw.setFixedHeight(46)
        self._sw.mode_changed.connect(self._on_spc)
        self._sw.setToolTip("点击右下角波谱按钮切换：Liquid / Aurora / Pulse / Particle")
        self._sw_fx=QGraphicsOpacityEffect(self._sw);self._sw.setGraphicsEffect(self._sw_fx);self._sw_fx.setOpacity(1.0)
        self._sw_anim=QPropertyAnimation(self._sw_fx,b"opacity",self);self._sw_anim.setDuration(180);self._sw_anim.setEasingCurve(QEasingCurve.OutCubic)
        swl.addWidget(self._sw);p0l.addWidget(sw_margin)

        # ═══ 歌曲列表（带分组 delegate + 拖拽排序） ═══
        self._list=QListWidget();self._list.setFrameShape(QFrame.NoFrame)
        self._list.setStyleSheet(
            f"QListWidget{{background:transparent;border:none;outline:none;}}"
            f"QListWidget::item{{color:{C_TEXT2};font-size:10px;padding:0;margin:0;border:none;background:transparent;}}")
        self._list_delegate=SongItemDelegate(self._list)
        self._list.setItemDelegate(self._list_delegate)
        self._list.itemDoubleClicked.connect(self._on_play)
        self._list_fx=QGraphicsOpacityEffect(self._list);self._list.setGraphicsEffect(self._list_fx);self._list_fx.setOpacity(1.0)
        self._list_anim=QPropertyAnimation(self._list_fx,b"opacity",self);self._list_anim.setDuration(180);self._list_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._list.setDragDropMode(QAbstractItemView.InternalMove)
        self._list.setDragEnabled(True);self._list.setDefaultDropAction(Qt.MoveAction)
        self._list.model().rowsMoved.connect(self._on_rows_moved)
        p0l.addWidget(self._list,stretch=1)
        self._stack.addWidget(p0)

        self._ag=AlbumGrid();self._ag.album_clicked.connect(self._show_album)
        self._stack.addWidget(self._ag)
        mid.addWidget(self._stack,stretch=1);ml.addLayout(mid,stretch=1)
        
        self._eq=EqPanel();self._eq.hide();ml.addWidget(self._eq)
        self._bb=BottomBar();ml.addWidget(self._bb)

        # Toast + 悬浮提示
        self._toast=ToastW(self);self._toast.show_msg("♩ OpenMusic")
        self._tip=TipW()

        # 场景覆盖层
        self._overlay=SceneOverlay(c)
        self._overlay.setGeometry(c.rect())
        # 合并resize：背景 + 覆盖层
        def _on_resize(ev):
            QWidget.resizeEvent(c,ev)
            bg_w.setGeometry(c.rect())
            self._overlay.setGeometry(c.rect())
        c.resizeEvent=_on_resize

        # 播放指示条动画
        self._bars_list=["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
        self._bar_idx=0
        self._bar_tm=QTimer(self);self._bar_tm.timeout.connect(self._tick_bar)
        self._list._play_bar_idx=0  # 给delegate用

        # 音量波纹 + 动态图标（静音、低、高三种样式）
        def _update_vol_icon(v):
            self._bb._mt._vol_level=v
            self._bb._mt.update()
            self._overlay.click_ripple(
                self._bb._mt.mapTo(c,self._bb._mt.rect().center()).x(),
                self._bb._mt.mapTo(c,self._bb._mt.rect().center()).y())
        self._bb._vs.valueChanged.connect(_update_vol_icon)
        # 侧边栏阴影
        add_shadow(self._lp,6,2,0,QColor(0,0,0,60))
        # 底部栏阴影
        add_shadow(self._bb,12,0,-4,QColor(0,0,0,100))

        # 信号
        self._lp.cat_sig.connect(self._on_cat)
        self._bb.pp_sig.connect(self._on_pp)
        self._bb.prv_sig.connect(self._prev);self._bb.nxt_sig.connect(self._next)
        self._bb.seek_sig.connect(self._audio.seek);self._bb.vol_sig.connect(self._audio.set_vol)
        self._bb.spec_sig.connect(lambda: self._sw.next_mode())
        self._bb.sleep_sig.connect(self._on_sleep);self._bb.eq_sig.connect(self._tog_eq)
        self._bb.mode_sig.connect(self._on_mode);self._bb.speed_sig.connect(self._audio.set_speed)
        try:
            self._bb._ly_btn.clicked.disconnect()
        except: pass
        self._bb._ly_btn.clicked.connect(self._toggle_lyrics)
        self._audio.pos_changed.connect(self._on_pos)
        self._audio.state_changed.connect(self._on_state)
        self._audio.track_ended.connect(self._next)
        QTimer.singleShot(200,self._scan)
        QTimer.singleShot(260,lambda: self._bb.set_mode(self._play_mode))

    def _load_state(self):
        try:
            if os.path.exists(STATE_FILE):
                data=json.loads(Path(STATE_FILE).read_text(encoding="utf-8"))
                self._fav_set=set(data.get("favorites",[]))
                self._play_mode=int(data.get("play_mode",1))
                self._listened_seconds=float(data.get("listened_seconds",0))
        except:
            self._fav_set=set();self._play_mode=1;self._listened_seconds=0
    def _save_state(self):
        try:
            os.makedirs(os.path.dirname(STATE_FILE),exist_ok=True)
            data={"favorites":sorted(self._fav_set),"play_mode":self._play_mode,
                "listened_seconds":round(self._listened_seconds,2)}
            Path(STATE_FILE).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
        except: pass
    def _fade_list(self):
        if not hasattr(self,'_list_anim'): return
        self._list_anim.stop();self._list_fx.setOpacity(0.62)
        self._list_anim.setStartValue(0.62);self._list_anim.setEndValue(1.0);self._list_anim.start()
    def _ripple_widget(self,widget):
        if not hasattr(self,'_overlay') or not widget: return
        if widget is self._list: return
        c=self.centralWidget()
        pt=widget.mapTo(c,widget.rect().center())
        self._overlay.click_ripple(pt.x(),pt.y())
    def _on_mode(self,idx,name):
        self._play_mode=idx;self._save_state()
        if hasattr(self,'_toast'): self._toast.show_msg(f"播放模式：{name}")

    def _scan(self):
        self._toast.show_msg("🔍 正在扫描曲库...")
        try:
            tracks=[]
            for ext in SE:
                for fp in Path(SD).rglob(f"*{ext}"):
                    if any(s in fp.parts for s in SK): continue
                    try: tracks.append(Meta.read(str(fp)))
                    except: 
                        import traceback; traceback.print_exc()
            tracks.sort(key=lambda t:(t['artist'],t['name']))
            self._lib=tracks;self._refresh()
            self._stats.update_stats(self._lib,self._fav_set,self._listened_seconds)
            if tracks:
                self._toast.show_msg(f"✅ 已加载 {len(tracks)} 首歌曲")
            else:
                self._toast.show_msg("⚠️ 未找到歌曲文件，请将音乐放在程序文件夹或桌面")
        except:
            import traceback; traceback.print_exc()
            self._toast.show_msg("❌ 曲库扫描出错，请检查文件")

    def _rebuild_list(self,ftsongs=None):
        """用 delegate 方式构建歌曲列表（含分组标题）"""
        self._list.clear()
        songs=ftsongs if ftsongs is not None else self._lib
        last_artist=""
        for t in songs:
            artist=t['artist'] or "未知歌手"
            if artist and artist!=last_artist:
                # 分组标题item
                hit=QListWidgetItem();hit.setText(f"— {artist} —")
                hit.setData(Qt.UserRole+2,"header");hit.setFlags(Qt.NoItemFlags)
                self._list.addItem(hit)
                last_artist=artist
            # 歌曲item
            it=QListWidgetItem(t['name'])
            it.setData(Qt.UserRole,t['path'])
            it.setData(Qt.UserRole+2,"song")
            it.setData(Qt.UserRole+4,t['artist'])
            it.setData(Qt.UserRole+5,fmt(t['dur']))
            it.setData(Qt.UserRole+3,Meta.cover(t['path']) or "")
            self._list.addItem(it)

    def _refresh(self,ft="",animate=True):
        self._list.clear()
        if ft:
            filtered=[t for t in self._lib if ft.lower() in t['name'].lower() or ft.lower() in t['artist'].lower()]
            self._rebuild_list(filtered)
        else: self._rebuild_list()
        if hasattr(self,'_stats'): self._stats.update_stats(self._lib,self._fav_set,self._listened_seconds)
        if animate: self._fade_list()

    def _filter(self,t): self._refresh(t,animate=False)

    def _on_sort(self):
        """循环切换排序：歌名↔歌手↔时长，每按一次切换升序/降序"""
        modes=["歌名","歌手","时长"]
        self._sort_asc=not self._sort_asc
        sm=(self._sort_mode+1 if self._sort_asc else self._sort_mode)%3
        self._sort_mode=sm
        arrow="↑" if self._sort_asc else "↓"
        if sm==0: self._lib.sort(key=lambda t:t['name'],reverse=not self._sort_asc)
        elif sm==1: self._lib.sort(key=lambda t:t['artist'],reverse=not self._sort_asc)
        else: self._lib.sort(key=lambda t:t['dur'],reverse=not self._sort_asc)
        self._refresh()
        self._toast.show_msg(f"排序：按{modes[sm]} {arrow}")

    def keyPressEvent(self,ev):
        if ev.key()==Qt.Key_Space:
            self._on_pp()
        elif ev.key()==Qt.Key_Left:
            self._prev()
        elif ev.key()==Qt.Key_Right:
            self._next()
        elif ev.key()==Qt.Key_F and (ev.modifiers()&Qt.ControlModifier):
            self._sch.setFocus()
        else:
            super().keyPressEvent(ev)

    def _page_title(self,base,cnt=0):
        """更新页面标题 + 歌曲数统计"""
        self._pg.setText(f"{base}"+(f"  · {cnt}首" if cnt else ""))
        self._page_lb.setText(base)

    def _on_cat(self,cat):
        self._fade_list()
        if cat=="专辑":
            self._page_title("专辑");self._stack.setCurrentIndex(1);self._refresh_albums()
        elif cat=="歌手":
            self._page_title("歌手",len(self._lib));self._stack.setCurrentIndex(0);self._refresh_artists()
        elif cat=="随机播放":
            if self._lib: self._play(random.choice(self._lib)['path'])
            self._stack.setCurrentIndex(0)
        elif cat=="播放历史":
            self._stack.setCurrentIndex(0);self._list.clear()
            self._page_title("播放历史",len(self._audio._history))
            for p in list(self._audio._history)[::-1]:
                for t in self._lib:
                    if t['path']==p:
                        it=QListWidgetItem(t['name'])
                        it.setData(Qt.UserRole,p)
                        it.setData(Qt.UserRole+2,"song")
                        it.setData(Qt.UserRole+4,t['artist'])
                        it.setData(Qt.UserRole+5,fmt(t['dur']))
                        it.setData(Qt.UserRole+3,Meta.cover(t['path']) or "")
                        self._list.addItem(it);break
            self._fade_list()
        elif cat=="收藏":
            self._stack.setCurrentIndex(0);self._list.clear()
            fav_cnt=0
            for t in self._lib:
                if t['path'] in self._fav_set:
                    it=QListWidgetItem(t['name'])
                    it.setData(Qt.UserRole,t['path'])
                    it.setData(Qt.UserRole+2,"song")
                    it.setData(Qt.UserRole+4,t['artist'])
                    it.setData(Qt.UserRole+5,fmt(t['dur']))
                    it.setData(Qt.UserRole+3,Meta.cover(t['path']) or "")
                    self._list.addItem(it);fav_cnt+=1
            self._page_title("我的收藏",fav_cnt)
            self._fade_list()
        elif cat=="最近添加":
            self._stack.setCurrentIndex(0)
            recent=sorted(self._lib,key=lambda t: os.path.getmtime(t['path']) if os.path.exists(t['path']) else 0,reverse=True)[:50]
            self._rebuild_list(recent)
            self._page_title("最近添加",len(recent))
            self._fade_list()
        else:
            self._page_title("全部音乐",len(self._lib));self._stack.setCurrentIndex(0);self._refresh()
    def _refresh_albums(self):
        albums={}
        for t in self._lib:
            an=t['album'] or "未知专辑"
            if an not in albums:
                cover=Meta.cover(t['path'])
                albums[an]={'name':an,'artist':t['artist'],'cover':cover,'count':0}
            albums[an]['count']+=1
            if t['artist'] and not albums[an]['artist']: albums[an]['artist']=t['artist']
        self._ag.set_albums([(i['name'],i['artist'],i['cover'],i['count']) for i in sorted(albums.values(),key=lambda x:x['name'])])
    def _refresh_artists(self):
        """按歌手分组显示"""
        artists={}
        for t in self._lib:
            ar=t['artist'] or "未知歌手"
            if ar not in artists: artists[ar]=0
            artists[ar]+=1
        self._list.clear()
        for ar,cnt in sorted(artists.items(),key=lambda x:-x[1]):
            it=QListWidgetItem(f"  {ar}  ({cnt}首)")
            it.setData(Qt.UserRole,f"__artist__{ar}")
            it.setData(Qt.UserRole+2,"song")
            self._list.addItem(it)
        self._fade_list()
    def _show_album(self,album):
        self._stack.setCurrentIndex(0);self._pg.setText(f"专辑 · {album}");self._page_lb.setText(f"专辑 · {album}")
        self._list.clear()
        for t in self._lib:
            if (t['album'] or "未知专辑")==album:
                it=QListWidgetItem(t['name'])
                it.setData(Qt.UserRole,t['path'])
                it.setData(Qt.UserRole+2,"song")
                it.setData(Qt.UserRole+4,t['artist'])
                it.setData(Qt.UserRole+5,fmt(t['dur']))
                it.setData(Qt.UserRole+3,Meta.cover(t['path']) or "")
                self._list.addItem(it)
        self._fade_list()
    def _on_play(self,item):
        if item.data(Qt.UserRole+2)!="song": return
        p=item.data(Qt.UserRole)
        if isinstance(p,str) and p.startswith("__artist__"):
            artist=p.replace("__artist__","")
            self._pg.setText(f"歌手 · {artist}");self._page_lb.setText(f"歌手 · {artist}")
            self._list.clear()
            for t in self._lib:
                if t['artist']==artist:
                    it=QListWidgetItem(t['name'])
                    it.setData(Qt.UserRole,t['path'])
                    it.setData(Qt.UserRole+2,"song")
                    it.setData(Qt.UserRole+4,t['artist'])
                    it.setData(Qt.UserRole+5,fmt(t['dur']))
                    it.setData(Qt.UserRole+3,Meta.cover(t['path']) or "")
                    self._list.addItem(it)
            self._fade_list()
            return
        if p and os.path.exists(p): self._play(p)
    def _fade_title(self,text):
        self._toast.show_msg(text)
    def _play(self,path):
        self._track_path=path
        for i,t in enumerate(self._lib):
            if t['path']==path: self._idx=i;break
        track=None
        for t in self._lib:
            if t['path']==path: track=t;break
        if track is None:
            m=Meta.read(path);track={'path':path,'name':m['name'],'artist':m['artist']}
        cover=Meta.cover(path)
        if cover: ColorMan().from_cover(cover)
        self._lyrics.load_for(path)
        self._overlay.set_glow(ColorMan().p,0)
        self._focus.update_song(track['name'],track['artist'],cover)
        # 更新底部栏
        self._bb.update_song(track['name'],track['artist'],cover)
        # 更新迷你播放信息模块
        self._mini_info.show()
        self._miti.setText(track['name'] or "")
        self._miar.setText(track['artist'] or "")
        if cover and os.path.exists(cover):
            px=QPixmap(cover).scaled(32,32,Qt.KeepAspectRatio,Qt.SmoothTransformation)
            self._micv.setPixmap(px)
            self._micv.setStyleSheet(f"border-radius:8px;border:1px solid rgba(77,225,193,45);")
        else:
            self._micv.setText("♩");self._micv.setStyleSheet(f"color:{C_TEXT3};font-size:16px;background:{C_DIVIDER};border-radius:8px;")
        self._fade_title(f"正在播放: {track['name']} — {track['artist']}")
        self.setWindowTitle(f"OpenMusic - {track['name']}")
        # 选中播放行
        self._list_delegate.set_playing(path)
        for i in range(self._list.count()):
            it=self._list.item(i)
            it.setSelected(it.data(Qt.UserRole)==path)
        self._list.viewport().update()
        self._audio.load(path)
    def _toggle_fav(self):
        if not self._track_path:
            self._toast.show_msg("请先播放一首歌曲")
            return
        if self._track_path in self._fav_set:
            self._fav_set.discard(self._track_path)
            self._toast.show_msg("♡ 已取消收藏")
            # 改变图标样式（临时变色提示）
            self._fav_btn._hover=True;self._fav_btn.update();QTimer.singleShot(300,lambda: (setattr(self._fav_btn,'_hover',False),self._fav_btn.update()))
        else:
            self._fav_set.add(self._track_path)
            self._toast.show_msg("♥ 已收藏")
            self._fav_btn._hover=True;self._fav_btn.update();QTimer.singleShot(300,lambda: (setattr(self._fav_btn,'_hover',False),self._fav_btn.update()))
        self._stats.update_stats(self._lib,self._fav_set,self._listened_seconds);self._save_state()
    def _on_pp(self):
        if not self._lib: return
        if not self._track_path: self._play(self._lib[0]['path']);return
        self._audio.toggle()
    def _prev(self):
        if not self._lib: return
        if self._play_mode==3:
            self._play(random.choice(self._lib)['path']);return
        if self._idx>0 and self._idx<len(self._lib): self._play(self._lib[self._idx-1]['path'])
        elif self._play_mode==1: self._play(self._lib[-1]['path'])
    def _next(self):
        if not self._lib: return
        if self._play_mode==2 and self._track_path:
            self._play(self._track_path);return
        if self._play_mode==3:
            self._play(random.choice(self._lib)['path']);return
        if self._idx<len(self._lib)-1: self._play(self._lib[self._idx+1]['path'])
        elif self._play_mode==1: self._play(self._lib[0]['path'])
        else: self._fade_title("播放列表已结束")
    def _on_pos(self,pos):
        now=time.time()
        if self._audio.state==Audio.P:
            if self._last_listen_tick is not None:
                delta=now-self._last_listen_tick
                if 0<delta<2:
                    self._listened_seconds+=delta
                    if int(self._listened_seconds)%10==0:
                        self._stats.update_stats(self._lib,self._fav_set,self._listened_seconds)
            self._last_listen_tick=now
        self._bb.update_pos(pos,self._audio.dur);self._sw._ana.feed(self._audio.spec_data())
        self._lyrics.update_pos(pos)
        cm=ColorMan()
        self._overlay.set_glow(cm.p,self._sw._ana.en)
    def _on_state(self,st):
        self._bb.update_play(st==Audio.P)
        if st==Audio.P:
            self._last_listen_tick=time.time()
            self._bar_tm.start(100)
            # 播放按钮中心 → 覆盖层坐标系
            c=self.centralWidget()
            btn_center=self._bb._pp.mapTo(c,self._bb._pp.rect().center())
            self._overlay.burst(btn_center.x(),btn_center.y())
            cm=ColorMan()
            self._overlay.set_glow(cm.p,self._sw._ana.en)
        else:
            self._last_listen_tick=None;self._save_state()
            self._bar_tm.stop()
    def _tick_bar(self):
        """更新当前播放行的跳动条（通过delegate重绘）"""
        self._bar_idx=(self._bar_idx+1)%len(self._bars_list)
        self._list._play_bar_idx=self._bar_idx
        self._list.viewport().update()
    def _on_spc(self,m):
        name=SpecWidget.MODES[m] if 0<=m<len(SpecWidget.MODES) else "Spectrum"
        if hasattr(self,'_focus'): self._focus.set_mode_name(name)
        if hasattr(self,'_sw_anim'):
            self._sw_anim.stop();self._sw_fx.setOpacity(0.42)
            self._sw_anim.setStartValue(0.42);self._sw_anim.setEndValue(1.0);self._sw_anim.start()
        self._ripple_widget(self._sw)
        self._toast.show_msg(f"波谱：{name}")

    def _on_rows_moved(self,parent,start,end,dest,row):
        """拖拽列表项后更新lib顺序"""
        # 重建self._lib为列表当前顺序（跳过header）
        new_order=[]
        for i in range(self._list.count()):
            it=self._list.item(i)
            if it and it.data(Qt.UserRole+2)=="song":
                p=it.data(Qt.UserRole)
                for t in self._lib:
                    if t['path']==p:
                        new_order.append(t);break
        if new_order:
            self._lib=new_order
            self._toast.show_msg("已更新列表顺序")
    def _tog_eq(self): self._eq.setVisible(not self._eq.isVisible())
    def _toggle_lyrics(self):
        self._lyrics.setVisible(not self._lyrics.isVisible())
        self._toast.show_msg("歌词面板已开启" if self._lyrics.isVisible() else "歌词面板已隐藏")
    def _on_sleep(self):
        items=["关闭","30分钟后","60分钟后","90分钟后"]
        choice,ok=QInputDialog.getItem(self,"睡眠定时","选择时间:",items,0,False)
        if not ok or choice=="关闭":
            if self._sleep_timer: self._sleep_timer.stop();self._sleep_timer=None
            self._fade_title("睡眠定时已取消");return
        mins={"30分钟后":30,"60分钟后":60,"90分钟后":90}[choice]
        if self._sleep_timer: self._sleep_timer.stop()
        self._sleep_timer=QTimer(self);self._sleep_timer.setSingleShot(True)
        self._sleep_timer.timeout.connect(lambda: (self._audio.stop(),self._fade_title("⏰ 睡眠定时到点")))
        self._sleep_timer.start(mins*60000)
        self._fade_title(f"⏰ {mins}分钟后停止播放")
    def _toggle_mini(self):
        if hasattr(self,'_is_mini') and self._is_mini:
            self.showNormal();self._is_mini=False
            for w in [self._lp,self._stack]: w.show()
            if self._eq_was_visible: self._eq.show()
        else:
            self._is_mini=True;self._eq_was_visible=self._eq.isVisible()
            for w in [self._lp,self._stack,self._eq]: w.hide()
            self.adjustSize()
            self.resize(self.width(),self._bb.height()+self.findChildren(QFrame)[0].height()+60)
    def dragEnterEvent(self,ev):
        if ev.mimeData().hasUrls(): ev.acceptProposedAction()
    def dropEvent(self,ev):
        for url in ev.mimeData().urls():
            p=url.toLocalFile()
            if os.path.isdir(p):
                for ext in SE:
                    for fp in Path(p).rglob(f"*{ext}"):
                        try: self._lib.append(Meta.read(str(fp)))
                        except: pass
            elif os.path.splitext(p)[1].lower() in SE:
                try: self._lib.append(Meta.read(p))
                except: pass
        self._lib.sort(key=lambda t:(t['artist'],t['name']));self._refresh();self._fade_title("已添加文件")
    def closeEvent(self,ev):
        if self._sleep_timer: self._sleep_timer.stop()
        self._save_state()
        self._audio.close();pygame.quit();ev.accept()

if __name__=="__main__":
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app=QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei UI" if sys.platform=="win32" else "PingFang SC",9))
    app.setStyle("Fusion")
    w=MainW();w.show();sys.exit(app.exec())
