import {api} from '../api/client.js';
import {workspace} from '../stores/workspace.js';
import {heading} from '../components/common/shell.js';
import {chart} from '../components/common/chart.js';
import {esc,date} from '../utils/dom.js';
export async function overview(){
 const [o,jobs,audits]=await Promise.all([api('/overview'),api('/jobs'),api('/audits')]),m=workspace.meta,baseline=jobs.find(j=>j.status==='completed');
 return heading('01 / DAILY BRIEF',m.name,m.workflow,'<a class="button primary" href="#/workbench">'+esc(m.action_label||'发起分析')+' ↗</a>')+'<section class="overview-hero"><div class="narrative"><p class="eyebrow">当前业务判断</p><h2>'+esc(baseline?.result?.summary||'先导入一批真实业务记录，形成可复核的分析结论。')+'</h2><p>'+esc(m.upstream)+' → '+esc(m.downstream)+'</p><a href="#/results" class="text-link">查看计算依据与业务解释 ↗</a></div><div class="numbers">'+[['业务记录',o.records],['数据批次',o.datasets],['分析任务',o.jobs],['已批准结果',o.approved]].map(([k,v])=>'<div><span>'+k+'</span><strong>'+v+'</strong></div>').join('')+'</div></section><section class="panel"><div class="section-title"><h2>基线切片</h2><span>来自 Python 计算 · '+esc(m.method)+'</span></div>'+chart(baseline?.result?.chart)+'</section><div class="two-columns"><section class="panel"><div class="section-title"><h2>今天需要回答</h2></div><ol class="questions">'+m.pains.map(v=>'<li>'+esc(v)+'</li>').join('')+'</ol></section><section class="panel"><div class="section-title"><h2>最近动作</h2><span>可追溯记录</span></div><ul class="timeline">'+audits.slice(0,4).map(a=>'<li><strong>'+esc(a.action)+'</strong><span>'+esc(a.actor)+' · '+date(a.at)+'</span></li>').join('')+'</ul></section></div>';
}
