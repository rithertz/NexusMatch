import type { Bracket, Health, Match, Player, Registration, Team, Tournament } from '../types/api'
const base = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1').replace(/\/$/, '')
export class ApiError extends Error { constructor(public status:number, message:string){super(message)} }
async function request<T>(path:string, options:RequestInit = {}):Promise<T>{
  let response:Response
  try { response = await fetch(`${base}${path}`, { ...options, headers:{'Content-Type':'application/json', ...options.headers} }) } catch { throw new ApiError(0, 'Unable to reach the API. Start the backend and check VITE_API_BASE_URL.') }
  const body = await response.json().catch(()=>null)
  if(!response.ok) throw new ApiError(response.status, body?.detail || `Request failed (${response.status}).`)
  return body as T
}
const q=(params:Record<string,string|number|undefined>)=>{const s=new URLSearchParams();Object.entries(params).forEach(([k,v])=>v!==undefined&&v!==''&&s.set(k,String(v)));return s.toString()?`?${s}`:''}
export const api={
 health:()=>request<Health>('/health'), tournaments:(p:Record<string,string|number|undefined>={})=>request<Tournament[]>(`/tournaments${q(p)}`), tournament:(id:number)=>request<Tournament>(`/tournaments/${id}`),
 createTournament:(body:Partial<Tournament>)=>request<Tournament>('/tournaments',{method:'POST',body:JSON.stringify(body)}), updateTournament:(id:number,body:Partial<Tournament>)=>request<Tournament>(`/tournaments/${id}`,{method:'PATCH',body:JSON.stringify(body)}),
 players:(p:Record<string,string|number|undefined>={})=>request<Player[]>(`/players${q(p)}`), teams:(p:Record<string,string|number|undefined>={})=>request<Team[]>(`/teams${q(p)}`), teamMembers:(id:number)=>request<{team_id:number;player_id:number;joined_at:string}[]>(`/teams/${id}/members`),
 registrations:(p:Record<string,string|number|undefined>={})=>request<Registration[]>(`/registrations${q(p)}`), register:(body:{tournament_id:number;player_id?:number;team_id?:number})=>request<Registration>('/registrations',{method:'POST',body:JSON.stringify(body)}), registrationStatus:(id:number,status:'approved'|'rejected')=>request<Registration>(`/registrations/${id}/status`,{method:'PATCH',body:JSON.stringify({status})}), withdraw:(id:number)=>request<Registration>(`/registrations/${id}/withdraw`,{method:'POST'}),
 bracket:(id:number)=>request<Bracket>(`/tournaments/${id}/bracket`), generateBracket:(id:number)=>request<Bracket>(`/tournaments/${id}/bracket`,{method:'POST'}), result:(tournamentId:number,matchId:number,body:{winner_registration_id:number;scores:{registration_id:number;score:number}[]})=>request<Match>(`/tournaments/${tournamentId}/matches/${matchId}/result`,{method:'POST',body:JSON.stringify(body)})
}
