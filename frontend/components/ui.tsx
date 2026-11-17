"use client";
import { X } from "lucide-react";
export function PageHeader({title,description,action}:{title:string;description?:string;action?:React.ReactNode}){return <div className="page-header"><div><h1>{title}</h1>{description&&<p>{description}</p>}</div>{action}</div>}
export function Skeleton({className=""}:{className?:string}){return <div className={`skeleton ${className}`}/>}
export function EmptyState({title,detail}:{title:string;detail:string}){return <div className="empty"><b>{title}</b><span>{detail}</span></div>}
export function Dialog({open,onClose,title,children}:{open:boolean;onClose:()=>void;title:string;children:React.ReactNode}){if(!open)return null;return <div className="overlay" role="dialog" aria-modal="true" onMouseDown={onClose}><section className="dialog" onMouseDown={e=>e.stopPropagation()}><header><h2>{title}</h2><button aria-label="Close" onClick={onClose}><X size={18}/></button></header>{children}</section></div>}
