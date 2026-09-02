const API=window.IRONCOACH_API||localStorage.getItem("ironcoach_api")||"https://ironcoach-api.onrender.com";
async function parse(r){const d=await r.json().catch(()=>({}));if(!r.ok)throw Error(d.detail||"Error de autenticación");return d}
export async function registerUser(name,email,password){return parse(await fetch(API+"/auth/register",{method:"POST",credentials:"include",headers:{"Content-Type":"application/json"},body:JSON.stringify({name,email,password})}))}
export async function loginUser(email,password){const body=new URLSearchParams({username:email,password});return parse(await fetch(API+"/auth/login",{method:"POST",credentials:"include",headers:{"Content-Type":"application/x-www-form-urlencoded"},body}))}
export async function logoutUser(){await fetch(API+"/auth/logout",{method:"POST",credentials:"include"}).catch(()=>{})}
export function saveToken(){localStorage.removeItem("ironcoach_token")}
export function logout(){logoutUser().finally(()=>{localStorage.removeItem("ironcoach_tab");localStorage.removeItem("ironcoach_onboarding");location.reload()})}
