export type LeadStatus = "new" | "contacted" | "qualified" | "booked" | "won" | "lost";

export type User = { id: number; email: string; name: string; role: "admin" | "member"; active: boolean };
export type Team = { id: number; name: string; timezone: string };
export type Me = { user: User; team: Team };
export type TeamUser = User & { team_id: number };

export type LeadListItem = {
  id: number;
  name: string;
  email: string | null;
  phone: string | null;
  status: LeadStatus;
  score: number;
  owner_id: number | null;
  source_id: number | null;
  created_at: string;
};
export type LeadsPage = { items: LeadListItem[]; total: number; page: number; page_size: number };
export type LeadEvent = {id:number;event_type:string;payload:Record<string,unknown>;actor_id:number|null;created_at:string};
export type Followup={id:number;lead_id:number;kind:string;channel:string;subject:string|null;body:string|null;due_at:string;sent_at:string|null;cancelled_at:string|null};
export type Appointment={id:number;lead_id:number;starts_at:string;ends_at:string;timezone:string;status:string;cancelled_at:string|null};

export type Source = {
  id: number;
  name: string;
  type: string;
  utm_defaults: Record<string, string>;
  public_capture_path: string;
  webhook_path: string;
};
export type WeeklyStats = {
  leads_per_source: { source: string; count: number }[];
  avg_first_response_minutes: number | null;
  conversion_by_stage: { status: LeadStatus; share: number }[];
  booking_rate: number;
  change_vs_previous_week: {
    total_leads: { absolute: number | null; percent: number | null };
    booking_rate: { absolute: number | null; percent: number | null };
    avg_response_time: { absolute: number | null; percent: number | null };
  };
};

export type Overview = {
  totals: {
    total_leads: number;
    hot_leads: number;
    new_this_week: number;
    qualified: number;
    booked: number;
    won: number;
    lost: number;
  };
  conversion_rate: number;
  leads_per_day: { date: string; count: number }[];
  leads_by_source: { source: string; count: number }[];
  funnel: { status: LeadStatus; count: number }[];
  needs_attention: { id: number; name: string; score: number }[];
  todays_appointments: { id: number; lead_id: number; starts_at: string }[];
};
