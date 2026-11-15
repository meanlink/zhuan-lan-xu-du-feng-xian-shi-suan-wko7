import {ledger} from '../api/entities.js';
import {downloadFile} from '../api/client.js';
import {session} from '../stores/session.js';
import {heading} from '../components/common/shell.js';
import {table} from '../components/common/table.js';
import {LedgerKind,Settlement} from '../constants/enums.js';
import {esc,date,notify} from '../utils/dom.js';
import {submit} from '../hooks/forms.js';
const uuid=()=>crypto.randomUUID?crypto.randomUUID():'req-'+Date.now()+'-'+Math.random().toString(16).slice(2);
const COLUMNS=[{key:'time',label:'时间'},{key:'kind',label:'类型'},{key:'amount',label:'额度'},{key:'available',label:'可用余额'},{key:'held',label:'预占中'},{key:'job',label:'关联试验'},{key:'settlement',label:'结算下落'},{key:'actor',label:'操作者'},{key:'note',label:'备注'}];
export async function ledgerPage(){
 const [sum,entries]=await Promise.all([ledger.summary(),ledger.entries()]);
 const rows=entries.map(e=>({time:date(e.created_at),kind:LedgerKind[e.kind]||e.kind,amount:e.amount,available:e.available_after,held:e.held_after,job:e.job_name||'—',settlement:e.settlement?(Settlement[e.settlement]||e.settlement):'—',actor:e.actor,note:e.note||'—'}));
 const isAdmin=session.user.role==='admin';
 return heading('06 / LEDGER','预付试算账本','续读试算按样本量计费：每条样本 1 额度。创建试验先固定费用并预占，计算成功实扣、失败退回，逐笔可核对。','<div class="heading-actions"><button class="button" id="refresh-ledger">刷新账本 ↻</button><button class="button" id="export-ledger">下载流水 CSV ↓</button></div>')
 +'<section class="panel"><div class="section-title"><h2>账户余额</h2><span>预占中的额度随计算结果落定转实扣或退回</span></div><div class="metrics ledger-metrics">'
 +[['可用额度',sum.available,''],['预占中 · 待结算',sum.held,sum.pending_jobs+' 个试验'],['累计入账',sum.deposited,''],['累计实扣',sum.charged,''],['累计退回',sum.refunded,'']].map(([k,v,u])=>'<div><span>'+esc(k)+'</span><strong>'+esc(v)+'<small>'+esc(u)+'</small></strong></div>').join('')
 +'</div></section><div class="two-columns ledger-grid"><section class="panel"><div class="section-title"><h2>登记入账</h2><span>仅业务负责人</span></div>'
 +(isAdmin?'<form id="deposit-form"><label>入账额度（正整数）<input name="amount" type="number" min="1" max="1000000" step="1" value="1000" required></label><label>备注<input name="note" maxlength="200" placeholder="例如：11 月试算额度预付"></label><button type="submit" class="primary">登记入账 ↗</button><p class="hint">入账立即计入可用余额；同一表单未修改内容重复提交只记一笔。</p></form>':'<p class="hint">当前角色可逐笔核对流水与余额；入账由业务负责人登记。</p>')
 +'</section><section class="method-sheet compact"><p class="eyebrow">BILLING RULE</p><h3>计费与结算口径</h3><ul><li>创建试验时按数据批次样本条数固定费用，并预占等额余额；余额不足整笔拒绝，不产生任何流水。</li><li>计算成功才实扣，失败退回预占；中断恢复沿用原费用，不重复扣退。</li><li>预占条目可从「待结算」追踪到「已扣款」或「已退回」；历史试验不追收费。</li></ul></section></div>'
 +'<section class="panel"><div class="section-title"><h2>账本流水</h2><span>'+entries.length+' 条 · 每笔含记账后余额</span></div>'+table(COLUMNS,rows,'尚无流水。先由负责人登记入账，再创建试验。')+'</section>';
}
export function bindLedger(refresh){
 let requestId=uuid();
 document.querySelector('#refresh-ledger').onclick=refresh;
 document.querySelector('#export-ledger').onclick=()=>downloadFile('/ledger/export','试算账本流水.csv').catch(e=>notify(e.message,true));
 const form=document.querySelector('#deposit-form');
 if(!form)return;
 form.addEventListener('input',()=>{requestId=uuid();});
 submit(form,async f=>{await ledger.deposit({amount:Number(f.get('amount')),note:f.get('note'),request_id:requestId});requestId=uuid();notify('入账已登记');await refresh();});
}
