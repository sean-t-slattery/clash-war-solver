export async function api<T>(path:string, body?:unknown):Promise<T> {
  const response = await fetch('/api'+path, body === undefined ? undefined : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  if(!response.ok){ const data = await response.json().catch(()=>({detail:response.statusText})); throw new Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail)); }
  return response.json();
}
export function download(name:string, value:unknown){ const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'})); const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000); }
export const title = (name:string) => name.replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase());
export const percent = (v:number) => `${Math.round(v*100)}%`;
export const duration = (v:number) => `${Math.floor(v/60)}:${String(Math.floor(v%60)).padStart(2,'0')}`;
