import {notify} from '../utils/dom.js';
export function submit(form,handler){form.addEventListener('submit',async e=>{e.preventDefault();const button=form.querySelector('[type=submit]');button.disabled=true;try{await handler(new FormData(form));}catch(error){notify(error.message,true);}finally{button.disabled=false;}});}
