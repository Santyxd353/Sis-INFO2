import axios from 'axios'
import { useEffect, useRef, useState } from 'react'
import api from '../../api/axiosInstance'
import type { PaginatedResponse } from '../../api/types'

export function errorFields(error:unknown):Record<string,string> {
  if (!axios.isAxiosError(error) || !error.response?.data) return {detail:'No se pudo completar la operación. Intente nuevamente.'}
  const data:unknown = error.response.data
  if (typeof data === 'string') return {detail:'No se pudo completar la operación. Intente nuevamente.'}
  if (Array.isArray(data)) return {detail:data.map(String).join(' ')}
  if (!data || typeof data !== 'object') return {detail:'No se pudo completar la operación.'}
  return Object.fromEntries(Object.entries(data).map(([key,value])=>[key,Array.isArray(value)?value.join(' '):String(value)]))
}

export function usePaged<T>(url:string, params:Record<string,string|number>, revision=0, enabled=true) {
  const query = JSON.stringify(params)
  const key = `${url}|${query}|${revision}|${enabled}`
  const [state,setState] = useState<{key:string;data?:PaginatedResponse<T>;error?:string}>({key:''})
  useEffect(()=>{
    if (!enabled) return
    const controller = new AbortController()
    api.get<PaginatedResponse<T>>(url,{params:JSON.parse(query),signal:controller.signal}).then(({data})=>{
      if (!controller.signal.aborted) setState({key,data})
    }).catch((e:unknown)=>{
      if (!controller.signal.aborted) setState({key,error:Object.values(errorFields(e)).join(' ')})
    })
    return ()=>controller.abort()
  },[url,query,key,enabled])
  const current = state.key===key ? state : undefined
  return {items:current?.data?.results??[],count:current?.data?.count??0,error:current?.error??'',loading:enabled&&!current}
}

export function useOperation() {
  const lock = useRef(false)
  const [busy,setBusy] = useState(false)
  const [errors,setErrors] = useState<Record<string,string>>({})
  const [denied,setDenied] = useState(false)
  async function run(operation:()=>Promise<unknown>, success:()=>void, failure?:(status:number)=>void) {
    if (lock.current || denied) return
    lock.current=true;setBusy(true);setErrors({})
    try { await operation(); success() }
    catch(e:unknown) {
      setErrors(errorFields(e))
      if(axios.isAxiosError(e)) {
        if(e.response?.status===403) setDenied(true)
        failure?.(e.response?.status??0)
      }
    }
    finally { lock.current=false;setBusy(false) }
  }
  return {busy,errors,denied,run}
}
