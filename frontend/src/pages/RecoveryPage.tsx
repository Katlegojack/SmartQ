import { Navigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, errorMessage } from "../api";
import { useCurrentAccountQuery } from "../auth";
import { EmptyState, FormMessage, PageLoading, SectionHeader, StatusPill, WorkspaceShell } from "../components";

type Option={id:number;option_date:string;option_time:string;available_count:number;is_recommended:boolean;is_selected:boolean};
type Recommendation={id:number;booking_id:number;old_booking_date:string;old_booking_time:string;suggested_booking_date:string;suggested_booking_time:string;reason:string;status:string;options:Option[]};

export function RecoveryPage(){
  const account=useCurrentAccountQuery(); const client=useQueryClient();
  const recommendations=useQuery({queryKey:["recovery"],queryFn:()=>api<Recommendation[]>("/api/v1/rescheduling/recommendations/my/"),refetchInterval:15_000});
  const select=useMutation({mutationFn:(id:number)=>api(`/api/v1/rescheduling/options/${id}/select/`,{method:"POST"}),onSuccess:()=>client.invalidateQueries({queryKey:["recovery"]})});
  if(account.isLoading)return <PageLoading/>; if(!account.data)return <Navigate to="/login/" replace/>; if(account.data.role!=="customer")return <Navigate to="/app/" replace/>;
  return <WorkspaceShell account={account.data} title="Recovery" subtitle="Replacement options when a service interruption affects your visit."><FormMessage error={select.error?errorMessage(select.error):""}/><section className="surface"><SectionHeader eyebrow="Affected visits" title="Replacement options"/>{recommendations.isError?<FormMessage error={errorMessage(recommendations.error)}/>:recommendations.data?.length?<div className="recovery-list">{recommendations.data.map((rec)=><article className="recovery-card" key={rec.id}><div className="recovery-head"><div><span className="eyebrow">Booking #{rec.booking_id}</span><h3>{rec.reason||"Service interruption"}</h3><p>Original visit: {rec.old_booking_date} · {String(rec.old_booking_time).slice(0,5)}</p></div><StatusPill value={rec.status}/></div>{rec.status==="pending"?<div className="recovery-options">{rec.options.map((option)=><button key={option.id} disabled={select.isPending||option.available_count<=0} className={option.is_recommended?"recovery-option is-recommended":"recovery-option"} onClick={()=>select.mutate(option.id)}><span>{option.is_recommended?"Recommended":"Available"}</span><strong>{option.option_date}</strong><em>{String(option.option_time).slice(0,5)}</em><small>{option.available_count} places left</small></button>)}</div>:<p className="muted">This recovery choice has already been resolved.</p>}</article>)}</div>:<EmptyState title="No recovery action needed" detail="If an operational disruption affects your visit, replacement options will appear here."/>}</section></WorkspaceShell>;
}
