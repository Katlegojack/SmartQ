export type Role = "customer" | "receptionist" | "counter_staff" | "branch_manager" | "system_admin";

export interface Account {
  id: number;
  username: string;
  first_name: string;
  last_name: string;
  email: string;
  role: Role;
  branch_id: number | null;
  branch_name: string | null;
  date_of_birth: string;
  gender: string;
  disability_status: boolean;
}

export interface Branch {
  id: number;
  branch_code: string;
  name: string;
  address: string;
  city: string;
  opening_time: string;
  closing_time: string;
  is_active: boolean;
  created_at?: string;
}

export interface Service {
  id: number;
  service_code: string;
  name: string;
  description: string;
  average_service_time: number;
  is_active: boolean;
  created_at?: string;
}

export interface BranchService {
  id: number;
  branch: number;
  branch_name?: string;
  service?: number;
  service_id?: number;
  service_code?: string;
  service_name: string;
  description?: string;
  average_service_time?: number;
  max_bookings_per_slot: number;
  is_active: boolean;
  created_at?: string;
}

export interface QueueTicket {
  id: number;
  booking_id: number;
  queue_number: string;
  queue_type: "general" | "priority" | string;
  status: "waiting" | "serving" | "completed" | "no_show" | "cancelled" | string;
  assigned_counter: number | null;
  branch_name: string;
  service_name: string;
  booking_date: string;
  booking_time: string;
  checked_in_at: string | null;
  customer_name: string;
  created_at: string;
}

export interface QueuePrediction {
  queue_position: number;
  people_ahead: number;
  estimated_wait_time: number;
  [key: string]: unknown;
}

export interface CurrentQueue {
  ticket: QueueTicket;
  prediction: QueuePrediction;
}

export interface Booking {
  id: number;
  customer_name: string;
  source: "online" | "walk_in" | string;
  branch: number;
  branch_name: string;
  service: number;
  service_name: string;
  booking_date: string;
  booking_time: string;
  is_pregnant: boolean;
  status: "pending" | "confirmed" | "completed" | "cancelled" | "no_show" | string;
  checked_in_at: string | null;
  is_checked_in: boolean;
  created_at: string;
  queue_ticket: Pick<QueueTicket, "id" | "queue_number" | "queue_type" | "status"> | null;
}

export interface SlotAvailability {
  time: string;
  capacity: number;
  booked: number;
  remaining: number;
  is_available: boolean;
}

export interface AvailabilityResponse {
  branch: number;
  service: number;
  date: string;
  slot_duration_minutes: number;
  max_bookings_per_slot: number;
  slots: SlotAvailability[];
}

export interface Counter {
  id: number;
  branch: number;
  branch_name: string;
  counter_number: number;
  queue_type: string;
  status: "closed" | "open" | "paused" | string;
  assigned_staff: number | null;
  assigned_staff_username: string | null;
  is_staffed: boolean;
  created_at?: string;
}

export interface StaffAccount {
  id: number;
  username: string;
  first_name: string;
  last_name: string;
  email: string;
  role: Exclude<Role, "customer">;
  branch_id: number | null;
  branch_name: string | null;
  is_active: boolean;
  date_joined: string;
}

export interface ManagerDashboard {
  branch?: { id: number; name: string; city?: string; branch_code?: string };
  date?: string;
  total_customers?: number;
  waiting?: number;
  serving?: number;
  completed?: number;
  no_show?: number;
  average_wait_time?: number;
  counters?: Counter[];
  counter_summary?: {
    total?: number;
    open?: number;
    paused?: number;
    closed?: number;
    staffed?: number;
    unstaffed?: number;
    busy?: number;
  };
  queue_summary?: Record<string, number>;
  service_summary?: Array<Record<string, unknown>>;
  [key: string]: unknown;
}

export interface QueueEvent {
  id: number;
  event_type: string;
  source?: string;
  actor_username?: string | null;
  actor_role?: string | null;
  booking_id?: number | null;
  ticket_id?: number | null;
  counter_id?: number | null;
  branch_id?: number;
  service_id?: number | null;
  queue_number?: string | null;
  queue_type?: string | null;
  from_ticket_status?: string | null;
  to_ticket_status?: string | null;
  from_booking_status?: string | null;
  to_booking_status?: string | null;
  metadata?: Record<string, unknown>;
  occurred_at: string;
}

export interface RescheduleOption {
  id: number;
  branch_id?: number;
  branch_name?: string;
  service_id?: number;
  service_name?: string;
  booking_date?: string;
  booking_time?: string;
  estimated_wait_time?: number;
  [key: string]: unknown;
}

export interface RescheduleRecommendation {
  id: number;
  booking?: number;
  booking_id?: number;
  status?: string;
  reason?: string;
  options?: RescheduleOption[];
  [key: string]: unknown;
}
