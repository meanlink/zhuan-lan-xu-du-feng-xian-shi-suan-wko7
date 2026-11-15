/** @typedef {{id:number,name:string,source:string,rows:number,checksum:string}} Dataset */
/** @typedef {{id:number,name:string,dataset_id:number,status:string,result:Object,approved:boolean,fee:number,settlement:string}} AnalysisJob */
/** @typedef {{id:number,name:string,job_id:number,destination:string,next_run:number,enabled:boolean}} ReportSchedule */
/** @typedef {{available:number,held:number,deposited:number,charged:number,refunded:number,pending_jobs:number}} LedgerSummary */
/** @typedef {{id:number,kind:string,amount:number,available_after:number,held_after:number,job_id:number|null,job_name:string,settlement:string,actor:string,note:string,created_at:number}} LedgerEntry */
export {};
