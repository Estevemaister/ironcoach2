const API=window.IRONCOACH_API||localStorage.getItem("ironcoach_api")||"https://ironcoach-api.onrender.com";
const authHeaders=()=>{const t=localStorage.getItem("ironcoach_token");return t?{"Authorization":`Bearer ${t}`}:{}};
async function req(path,body){const r=await fetch(API+path,{method:"POST",credentials:"include",headers:{"Content-Type":"application/json",...authHeaders()},body:JSON.stringify(body)});const d=await r.json().catch(()=>({}));if(!r.ok)throw Error(d.detail||"No se ha podido guardar");return d}
export async function saveOnboarding(data){return req("/auth/onboarding",data)}
export async function generatePlan(limiter="bike"){const r=await fetch(API+`/plan/generate?race_date=2027-04-18&limiter=${encodeURIComponent(limiter)}`,{method:"POST",credentials:"include",headers:authHeaders()});const d=await r.json().catch(()=>({}));if(!r.ok)throw Error(d.detail||"No se ha podido generar el plan");return d}
