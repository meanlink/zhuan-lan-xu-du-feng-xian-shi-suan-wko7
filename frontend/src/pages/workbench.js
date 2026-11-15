import {datasets,jobs,ledger} from '../api/entities.js';
import {workspace} from '../stores/workspace.js';
import {session} from '../stores/session.js';
import {heading} from '../components/common/shell.js';
import {esc,notify} from '../utils/dom.js';
import {submit} from '../hooks/forms.js';
const uuid=()=>crypto.randomUUID?crypto.randomUUID():'req-'+Date.now()+'-'+Math.random().toString(16).slice(2);
const feeText=(rows,b)=>b?('本次预占 '+rows+' 额度（每条样本 1 额度）· 当前可用 '+b.available+' 额度'+(b.available<rows?'，余额不足将被整笔拒绝':'')):'本次预占 '+rows+' 额度（每条样本 1 额度）';
export async function workbench(){
 workspace.datasets=await datasets.list();const m=workspace.meta;
 workspace.balance=await ledger.summary().catch(()=>null);
 const first=workspace.datasets[0];
 return heading('03 / ANALYSIS LAB',m.workbench_title,'选择业务批次和分析口径。参数、输入指纹与计算结论随任务保存，便于复核和复现。')+'<div class="workbench-grid"><section class="panel"><form id="job-form"><label>分析任务名称<input name="name" required minlength="2" value="'+esc(m.name)+' · 复核试算"></label><label>数据批次<select name="dataset_id" required>'+workspace.datasets.map(d=>'<option value="'+d.id+'">'+esc(d.name)+' · '+d.rows+' 条</option>').join('')+'</select></label><div class="parameter-grid">'+m.parameters.map(p=>'<label>'+esc(p.label)+(p.type==='select'?'<select name="param-'+esc(p.key)+'">'+p.options.map(o=>'<option value="'+esc(o.value)+'" '+(o.value==p.default?'selected':'')+'>'+esc(o.label)+'</option>').join('')+'</select>':'<input type="number" step="any" name="param-'+esc(p.key)+'" value="'+esc(p.default)+'" min="'+esc(p.min??'')+'" max="'+esc(p.max??'')+'" required>')+'</label>').join('')+'</div><p id="fee-hint" class="hint fee-hint'+(first&&workspace.balance&&workspace.balance.available<first.rows?' warn':'')+'">'+(first?esc(feeText(first.rows,workspace.balance)):'')+'</p><button type="submit" class="primary" '+(session.user.role==='viewer'||!workspace.datasets.length?'disabled':'')+'>'+esc(m.action_label||'执行分析')+' ↗</button><p class="hint">提交后由后台任务计算，成功才实扣、失败退回预占。观察员可查看参数和结果，无法提交。</p></form></section><section class="method-sheet"><p class="eyebrow">METHOD / BUSINESS RULE</p><h2>'+esc(m.method)+'</h2><p>'+esc(m.tagline)+'</p><h3>业务判读边界</h3><ul>'+m.limitations.map(v=>'<li>'+esc(v)+'</li>').join('')+'</ul><div class="method-trace"><span>输入</span><strong>'+esc(m.dataset_name)+'</strong><span>输出</span><strong>可复核结果 / 参数版本 / 分发归档</strong></div></section></div>';
}
export function bindWorkbench(){
 let requestId=uuid();
 const form=document.querySelector('#job-form'),select=form.querySelector('[name=dataset_id]'),hint=document.querySelector('#fee-hint');
 const updateFee=()=>{const d=workspace.datasets.find(x=>x.id===Number(select.value));if(!d||!hint)return;hint.textContent=feeText(d.rows,workspace.balance);hint.classList.toggle('warn',!!workspace.balance&&workspace.balance.available<d.rows);};
 select.addEventListener('change',updateFee);
 form.addEventListener('input',()=>{requestId=uuid();});  // 内容一变即换新请求号；未修改的重试沿用同号不重复扣款
 submit(form,async f=>{const params={};for(const p of workspace.meta.parameters){const value=f.get('param-'+p.key);params[p.key]=p.type==='number'?Number(value):value;}const j=await jobs.create({name:f.get('name'),dataset_id:Number(f.get('dataset_id')),params,request_id:requestId});requestId=uuid();workspace.selectedJob=j.id;notify('分析任务已提交，费用已预占');location.hash='#/results/'+j.id;});
}
