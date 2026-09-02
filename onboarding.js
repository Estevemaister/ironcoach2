const API=window.IRONCOACH_API||localStorage.getItem("ironcoach_api")||"https://ironcoach-api.onrender.com";
async function req(path,body){const r=await fetch(API+path,{method:"POST",credentials:"include",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});const d=await r.json().catch(()=>({}));if(!r.ok)throw Error(d.detail||"No se ha podido guardar");return d}
export async function saveOnboarding(data){return req("/auth/onboarding",data)}
export async function generatePlan(limiter="bike"){const r=await fetch(API+`/plan/generate?race_date=2027-04-18&limiter=${encodeURIComponent(limiter)}`,{method:"POST",credentials:"include"});const d=await r.json().catch(()=>({}));if(!r.ok)throw Error(d.detail||"No se ha podido generar el plan");return d}
