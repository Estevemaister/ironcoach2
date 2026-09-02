const API=window.IRONCOACH_API||localStorage.getItem("ironcoach_api")||"https://ironcoach-api.onrender.com";
const headers=()=>{const t=localStorage.getItem("ironcoach_token");return t?{"Authorization":"Bearer "+t}:{} };
async function parse(r){const d=await r.json().catch(()=>({}));if(!r.ok)throw Error(d.detail||"Error de autenticación");if(d.access_token)localStorage.setItem("ironcoach_token",d.access_token);return d}
export async function registerUser(name,email,password){return parse(await fetch(API+"/auth/register",{method:"POST",credentials:"include",headers:{"Content-Type":"application/json"},body:JSON.stringify({name,email,password})}))}
export async function loginUser(email,password){const body=new URLSearchParams({username:email,password});return parse(await fetch(API+"/auth/login",{method:"POST",credentials:"include",headers:{"Content-Type":"application/x-www-form-urlencoded"},body}))}
export async function logoutUser(){await fetch(API+"/auth/logout",{method:"POST",credentials:"include",headers:headers()}).catch(()=>{})}
export function saveToken(token){if(token)localStorage.setItem("ironcoach_token",token)}
export function logout(){logoutUser().finally(()=>{localStorage.removeItem("ironcoach_token");localStorage.removeItem("ironcoach_tab");localStorage.removeItem("ironcoach_onboarding");location.reload()})}
