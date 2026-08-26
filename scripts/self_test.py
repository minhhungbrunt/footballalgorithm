"""Offline sanity tests for the FootballEdge model. No network required."""
import importlib.util
from pathlib import Path

p=Path(__file__).with_name('update.py')
spec=importlib.util.spec_from_file_location('update',p)
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

def team(div,pos,last,form,gf,ga,xg=None,lineup=8.0,inj=0,transfer=0):
    return {"division":div,"position":pos,"lastSeasonPosition":last,"form":form,"formPoints":sum(3 if x=='W' else 1 if x=='D' else 0 for x in form),"recentGF":gf,"recentGA":ga,"xg":xg,"lineupAvgRating":lineup,"injuries":[{}]*inj,"transferImpact":transfer,"lineup":[{"name":str(i),"starter":True} for i in range(11)]}

def check(name,match,expect=None):
    r=m.model(match); v=r['verdict']; s=r['projected']; a,b=map(int,s.split('–'))
    if v.startswith('WIN: ') and v[5:]==match['home'] and not a>b: raise AssertionError(name+': home verdict conflicts with score')
    if v.startswith('WIN: ') and v[5:]==match['away'] and not b>a: raise AssertionError(name+': away verdict conflicts with score')
    if v=='DRAW' and a!=b: raise AssertionError(name+': draw verdict conflicts with score')
    if expect and v!=expect: raise AssertionError(name+f': expected {expect}, got {v}')
    print('PASS',name,v,s,r['probabilities'])

# Cross-division sanity: Championship side should not lose merely because it is away from League One.
check('cross-division',{
    'home':'Doncaster','away':'Middlesbrough','homeData':team('League One',2,8,'WLDLW',1.3,1.2),
    'awayData':team('Championship',10,4,'WWDWW',1.7,0.9), 'h2h':{}, 'h2hSummary':'N/A'
})
# Strong same-division side should generate a scoreline consistent with the verdict.
check('strong-home',{
    'home':'Strong FC','away':'Weak FC','homeData':team('Premier League',2,4,'WWWWW',2.3,.8,1.9,8.1,1),
    'awayData':team('Premier League',18,16,'LLLDL',.8,2.0,.8,7.0,3), 'h2h':{}, 'h2hSummary':'N/A'
})
print('ALL OFFLINE MODEL TESTS PASSED')
