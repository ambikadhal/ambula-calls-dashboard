"""Daily update: python3 update.py
Reads every .xlsx in data/ (sheet 'Calls', de-duplicated on Call ID), recomputes the plan,
and writes index.html (codes only: no referrer names, no phone numbers)."""
import pandas as pd, numpy as np, json, glob, os, sys
TARGETS={'CR':240000,'WB':51500,'OD':11500}; TH=240000; MILE=100000; MILE_DAY=15; PEAK_DAY=20; E=0.004
TNAME={'CR':'Craftzens','WB':'mDigital-ParisevaOne','OD':'mDigital-OD'}
TOPN={'CR':25,'WB':15,'OD':10}
SCOPE={'CR':['Telugu','Kannada','Marathi','Tamil','Punjabi','Gujarati','Malayalam'],'WB':['Bangla'],'OD':['Telugu']}
TELSPLIT={'CR':2350,'OD':650}
REG=['Telugu','Bangla','Kannada','Marathi','Tamil','Punjabi','Gujarati','Malayalam']
HIN=['Hindi','Bhojpuri','Haryanvi']
CR_START=6000   # Craftzens goal for the first plan day is never below this; every other team/company is raised by the same factor

files=sorted(glob.glob('data/*.xlsx'))
d=pd.concat([pd.read_excel(f,sheet_name='Calls') for f in files],ignore_index=True).drop_duplicates('Call ID')
dt=pd.to_datetime(d['Call date (IST)'],format='%d %b %Y, %I:%M %p')
d['date']=dt.dt.normalize(); d['hour']=dt.dt.hour
d['code']=d['Referral code'].astype(str).str.upper().str.replace(r'^[^A-Z0-9]+','',regex=True)
def team(c):
    if c.startswith(('CR','JSSK','SB')): return 'CR'
    if c.startswith('OD'): return 'OD'
    if c.startswith('WB'): return 'WB'
    return 'UN'
d['team']=d.code.map(team); d['hin']=d.Language.isin(HIN)
days=pd.date_range(d.date.min(),d.date.max()); ND=len(days); LAST=days[-1].day; REM=30-LAST; first=LAST+1
lab=[x.strftime('%a %-d %b') for x in days]
print(len(d),'calls',lab[0],'to',lab[-1],'REM',REM)

def plan(s0,rem):
    """daily goals first..30: start at s0 (yesterday level), rise linearly to peak on PEAK_DAY, then almost flat (+E/day)."""
    ds=list(range(first,31))
    if rem<=0: return [0]*len(ds),0
    c0=[];cp=[]
    for x in ds:
        if first<PEAK_DAY and x<=PEAK_DAY: t=(x-first)/(PEAK_DAY-first); c0.append(s0*(1-t)); cp.append(t)
        elif first<PEAK_DAY: c0.append(0); cp.append(1+E*(x-PEAK_DAY))
        else: c0.append(0); cp.append(1+E*(x-first))
    P=(rem-sum(c0))/sum(cp)
    if P<s0: g=[rem/len(ds)]*len(ds); P=rem/len(ds)    # already ahead of schedule: hold flat
    else: g=[a+b*P for a,b in zip(c0,cp)]
    return g,P
def series(hd,done,target):
    b7=float(hd[-7:].mean()); y=float(hd[-1]); s0=max(y,b7)*F; rem=target-done
    g,P=plan(s0,rem); cum=(done+np.cumsum(g)).tolist()
    x=np.arange(1,ND); sl,ic=np.polyfit(x,hd[1:],1)
    fit=np.maximum(ic+sl*np.arange(ND,30),0)
    M=target*MILE/TH
    cross=next((first+i for i,v in enumerate(cum) if v>=M),None)
    pace=None
    if b7>0:
        k=(M-done)/b7; pace=None if k>REM else first+int(np.ceil(max(k,1))) -1
    need15=(M-done)/(MILE_DAY-LAST) if LAST<MILE_DAY else None
    return dict(target=target,hindi=int(done),remaining=int(rem),req=rem/REM,b7=b7,yest=y,s0=s0,peak=P,uplift=g[0]/b7 if b7 else 0,
      goal=g,cum=cum,hd=hd.tolist(),cumact=np.cumsum(hd).tolist(),flat=float(done+REM*b7),trend=float(done+fit.sum()),
      trendpath=(done+np.cumsum(fit)).tolist(),flatpath=(done+np.cumsum([b7]*REM)).tolist(),
      mile=dict(target=float(M),gap=float(M-done),cross=cross,pace_cross=pace,need15=need15,done_pct=float(done/M)),
      ckpt={str(n):int(round(cum[n-first],-2)) for n in (15,20,25,30) if n>=first})
_c=d[(d.team=='CR')&d.hin].groupby('date').size().reindex(days,fill_value=0).values
F=max(1.0,CR_START/max(_c[-1],_c[-7:].mean()))
print('start factor',round(F,3))
hs=d[d.hin]; hsum=int(hs.groupby('date').size().reindex(days,fill_value=0).sum())
chd=hs.groupby('date').size().reindex(days,fill_value=0).values
out={'days':lab,'dnum':[x.day for x in days],'LAST':LAST,'REM':REM,'milestone':MILE,'F':F,'mileDay':MILE_DAY,'peakDay':PEAK_DAY,
 'co':series(chd,hsum,TH)}
out['co'].update(calls=len(d),odia=int((d.Language=='Odia').sum()),eng=int((d.Language=='English').sum()),
 reg={l:int((d.Language==l).sum()) for l in REG},unassigned=int(hs[hs.team=='UN'].shape[0]))
out['teams']={}
for T in TARGETS:
    S=d[d.team==T]; H=S[S.hin]
    hd=H.groupby('date').size().reindex(days,fill_value=0).values
    r=series(hd,len(H),TARGETS[T]); r.update(name=TNAME[T],calls=len(S),topn=TOPN[T])
    ratio=r['goal'][0]/r['b7'] if r['b7'] else 0
    c=H.groupby(['code','date']).size().unstack(fill_value=0).reindex(columns=days,fill_value=0)
    ct=S.groupby('code').size(); tt=c.sum(axis=1).sort_values(ascending=False)
    r['ncodes']=int(S.code.nunique()); r['top5share']=float(tt.head(5).sum()/max(len(H),1))
    r['top']=[dict(code=k,hindi=int(tt[k]),total=int(ct[k]),daily=c.loc[k].tolist()) for k in tt.head(TOPN[T]).index]
    chg=c[days[-5:]].mean(axis=1)-c[days[:5]].mean(axis=1); big=tt[tt>=60].index; rs=chg[big].sort_values()
    mk=lambda k:dict(code=k,a=float(c.loc[k,days[:5]].mean()),b=float(c.loc[k,days[-5:]].mean()))
    r['fall']=[mk(k) for k in rs.head(6).index if rs[k]<0]; r['rise']=[mk(k) for k in rs.tail(6).index[::-1] if rs[k]>0]
    dm=c[(c[days[:-3]].sum(axis=1)>=15)&(c[days[-3:]].sum(axis=1)==0)]
    r['dormant']=[dict(code=k,calls=int(dm.loc[k].sum()),last=lab[int(np.nonzero(dm.loc[k].values)[0][-1])]) for k in dm.sum(axis=1).sort_values(ascending=False).index[:10]]
    LR=[]
    for l in SCOPE[T]:
        own=int((S.Language==l).sum()); comp=int((d.Language==l).sum())
        tg=TELSPLIT[T] if l=='Telugu' else 1500; done=own if l=='Telugu' else comp
        LR.append(dict(lang=l,target=tg,done=done,own=own,comp=comp,perday=max(tg-done,0)/REM))
    r['langs']=LR
    h=H.groupby(['date','hour']).size().unstack(fill_value=0).reindex(index=days,columns=range(24),fill_value=0)
    r['heat']=h.values.tolist(); r['hourAvg']=h.loc[days[1:]].mean().round(1).tolist()
    am=H.groupby('date')['Patient mobile'].nunique().reindex(days,fill_value=0).values
    r['actmob']=am.tolist(); r['cpm']=float(hd[-7:].sum()/max(am[-7:].sum(),1)); r['b7mob']=float(am[-7:].mean())
    r['need_mob']=float(r['goal'][-1]/max(r['cpm'],1))
    out['teams'][T]=r
# code-wise rows (codes only)
a=d[d.team!='UN']; c=a[a.hin].groupby(['code','date']).size().unstack(fill_value=0).reindex(columns=days,fill_value=0)
tm=a.groupby('code').team.first(); al=a.groupby('code').size()
out['codes']=[[k,tm[k],int(c.loc[k].sum()),int(al[k]),c.loc[k].tolist()] for k in c.sum(axis=1).sort_values(ascending=False).index]
out['regTeam']={l:d[d.Language==l].groupby('team').size().to_dict() for l in REG}
tpl=open('tpl.html').read()
open('index.html','w').write(tpl.replace('/*DATA*/null',json.dumps(out,default=float)))
for T,r in out['teams'].items(): print(T,r['hindi'],'goal today',round(r['goal'][0]),'peak',round(r['peak']),'yest',int(r['yest']),'cum15',round(r['cum'][15-first]) if first<=15 else '-','cross',r['mile']['cross'])
c=out['co']; print('CO',c['hindi'],'goal today',round(c['goal'][0]),'peak',round(c['peak']),'cross',c['mile']['cross'])
