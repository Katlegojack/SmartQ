import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, errorMessage } from "../api";
import {
  EmptyState,
  Field,
  FormMessage,
  ProtectedWorkspace,
  SectionHeader,
  StatusPill,
} from "../components";
import type { Account, Branch, BranchService, Role, Service, StaffAccount } from "../types";

type AdminTab = "branches" | "services" | "capacity" | "staff";
type StaffRole = Exclude<Role, "customer">;

type WriteRequest = {
  path: string;
  method: "POST" | "PATCH";
  body: unknown;
};

const STAFF_ROLES: Array<{ value: StaffRole; label: string }> = [
  { value: "receptionist", label: "Receptionist" },
  { value: "counter_staff", label: "Counter Staff" },
  { value: "branch_manager", label: "Branch Manager" },
  { value: "system_admin", label: "System Admin" },
];

function AdminBody({ account }: { account: Account }) {
  const client = useQueryClient();
  const [tab, setTab] = useState<AdminTab>("branches");
  const [editingBranch, setEditingBranch] = useState<Branch | null>(null);
  const [editingService, setEditingService] = useState<Service | null>(null);
  const [editingMapping, setEditingMapping] = useState<BranchService | null>(null);
  const [editingStaff, setEditingStaff] = useState<StaffAccount | null>(null);
  const [staffRole, setStaffRole] = useState<StaffRole>("receptionist");
  const [message, setMessage] = useState("");
  const [formError, setFormError] = useState("");

  const branches = useQuery({
    queryKey: ["admin", "branches"],
    queryFn: () => api<Branch[]>("/api/v1/branches/admin/"),
  });
  const services = useQuery({
    queryKey: ["admin", "services"],
    queryFn: () => api<Service[]>("/api/v1/services/admin/"),
  });
  const mappings = useQuery({
    queryKey: ["admin", "mappings"],
    queryFn: () => api<BranchService[]>("/api/v1/services/admin/branch-services/"),
  });
  const staff = useQuery({
    queryKey: ["admin", "staff"],
    queryFn: () => api<StaffAccount[]>("/api/v1/accounts/admin/staff/"),
  });

  async function refresh() {
    await Promise.all([
      client.invalidateQueries({ queryKey: ["admin"] }),
      client.invalidateQueries({ queryKey: ["account"] }),
    ]);
  }

  function clearEditors() {
    setEditingBranch(null);
    setEditingService(null);
    setEditingMapping(null);
    setEditingStaff(null);
  }

  const write = useMutation({
    mutationFn: ({ path, method, body }: WriteRequest) => api(path, { method, body }),
    onSuccess: async () => {
      setMessage("Changes saved.");
      setFormError("");
      clearEditors();
      setStaffRole("receptionist");
      await refresh();
    },
    onError: (error) => setFormError(errorMessage(error, "Could not save these changes.")),
  });

  const activate = useMutation({
    mutationFn: ({ id, is_active }: { id: number; is_active: boolean }) =>
      api(`/api/v1/accounts/admin/staff/${id}/activation/`, {
        method: "PATCH",
        body: { is_active },
      }),
    onSuccess: async () => {
      setMessage("Account state updated.");
      setFormError("");
      await refresh();
    },
    onError: (error) => setFormError(errorMessage(error, "Could not update this account.")),
  });

  function switchTab(next: AdminTab) {
    setTab(next);
    setMessage("");
    setFormError("");
    clearEditors();
    setStaffRole("receptionist");
  }

  function branchSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const openingTime = String(form.get("opening_time") || "");
    const closingTime = String(form.get("closing_time") || "");
    if (openingTime && closingTime && openingTime >= closingTime) {
      setFormError("Closing time must be later than opening time.");
      return;
    }
    write.mutate({
      path: editingBranch ? `/api/v1/branches/admin/${editingBranch.id}/` : "/api/v1/branches/admin/",
      method: editingBranch ? "PATCH" : "POST",
      body: {
        branch_code: form.get("branch_code"),
        name: form.get("name"),
        address: form.get("address"),
        city: form.get("city"),
        opening_time: openingTime,
        closing_time: closingTime,
        is_active: form.get("is_active") === "on",
      },
    });
  }

  function serviceSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    write.mutate({
      path: editingService ? `/api/v1/services/admin/${editingService.id}/` : "/api/v1/services/admin/",
      method: editingService ? "PATCH" : "POST",
      body: {
        service_code: form.get("service_code"),
        name: form.get("name"),
        description: form.get("description"),
        average_service_time: Number(form.get("average_service_time")),
        is_active: form.get("is_active") === "on",
      },
    });
  }

  function mappingSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    if (editingMapping) {
      write.mutate({
        path: `/api/v1/services/admin/branch-services/${editingMapping.id}/`,
        method: "PATCH",
        body: {
          max_bookings_per_slot: Number(form.get("max_bookings_per_slot")),
          is_active: form.get("is_active") === "on",
        },
      });
      return;
    }
    write.mutate({
      path: "/api/v1/services/admin/branch-services/",
      method: "POST",
      body: {
        branch: Number(form.get("branch")),
        service: Number(form.get("service")),
        max_bookings_per_slot: Number(form.get("max_bookings_per_slot")),
        is_active: form.get("is_active") === "on",
      },
    });
  }

  function staffSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const branchValue = staffRole === "system_admin" ? null : Number(form.get("branch"));

    if (staffRole !== "system_admin" && !branchValue) {
      setFormError("Select an active branch for this staff role.");
      return;
    }

    if (editingStaff) {
      write.mutate({
        path: `/api/v1/accounts/admin/staff/${editingStaff.id}/`,
        method: "PATCH",
        body: {
          first_name: form.get("first_name"),
          last_name: form.get("last_name"),
          email: form.get("email"),
          role: staffRole,
          branch: branchValue,
        },
      });
      return;
    }

    write.mutate({
      path: "/api/v1/accounts/admin/staff/",
      method: "POST",
      body: {
        username: form.get("username"),
        password: form.get("password"),
        first_name: form.get("first_name"),
        last_name: form.get("last_name"),
        email: form.get("email"),
        date_of_birth: form.get("date_of_birth"),
        gender: form.get("gender"),
        disability_status: form.get("disability_status") === "on",
        role: staffRole,
        branch: branchValue,
      },
    });
  }

  return <>
    <div className="admin-tabs" role="tablist" aria-label="Administration areas">
      {(["branches", "services", "capacity", "staff"] as AdminTab[]).map((item) => (
        <button
          key={item}
          type="button"
          className={tab === item ? "is-active" : ""}
          onClick={() => switchTab(item)}
        >
          {item === "capacity" ? "Branch services" : item[0].toUpperCase() + item.slice(1)}
        </button>
      ))}
    </div>
    <FormMessage message={message} error={formError} />

    {tab === "branches" ? <div className="admin-split">
      <section className="surface">
        <SectionHeader eyebrow="Organization" title="Branches" />
        <div className="admin-list">
          {branches.data?.map((branch) => (
            <button
              type="button"
              key={branch.id}
              className={editingBranch?.id === branch.id ? "admin-list-row is-selected" : "admin-list-row"}
              onClick={() => { setEditingBranch(branch); setMessage(""); setFormError(""); }}
            >
              <div><strong>{branch.name}</strong><span>{branch.city} · {branch.branch_code}</span></div>
              <div><span>{branch.opening_time.slice(0, 5)}–{branch.closing_time.slice(0, 5)}</span><StatusPill value={branch.is_active ? "active" : "inactive"} /></div>
            </button>
          ))}
        </div>
      </section>
      <section className="surface">
        <SectionHeader
          eyebrow={editingBranch ? "Edit" : "Create"}
          title={editingBranch ? editingBranch.name : "New branch"}
          action={editingBranch ? <button type="button" className="text-action" onClick={() => setEditingBranch(null)}>New branch</button> : undefined}
        />
        <form key={editingBranch?.id || "new"} onSubmit={branchSubmit}>
          <div className="form-grid">
            <Field label="Branch code"><input name="branch_code" defaultValue={editingBranch?.branch_code || ""} required /></Field>
            <Field label="Name"><input name="name" defaultValue={editingBranch?.name || ""} required /></Field>
            <Field label="City"><input name="city" defaultValue={editingBranch?.city || ""} required /></Field>
            <Field label="Address"><input name="address" defaultValue={editingBranch?.address || ""} required /></Field>
            <Field label="Opening time"><input name="opening_time" type="time" defaultValue={editingBranch?.opening_time.slice(0, 5) || "08:00"} required /></Field>
            <Field label="Closing time"><input name="closing_time" type="time" defaultValue={editingBranch?.closing_time.slice(0, 5) || "17:00"} required /></Field>
          </div>
          <label className="check-field"><input name="is_active" type="checkbox" defaultChecked={editingBranch?.is_active ?? true} /><span>Active branch</span></label>
          <button className="button button--primary" disabled={write.isPending}>{editingBranch ? "Update branch" : "Create branch"}</button>
        </form>
      </section>
    </div> : null}

    {tab === "services" ? <div className="admin-split">
      <section className="surface">
        <SectionHeader eyebrow="Catalogue" title="Services" />
        <div className="admin-list">
          {services.data?.map((service) => (
            <button
              type="button"
              key={service.id}
              className={editingService?.id === service.id ? "admin-list-row is-selected" : "admin-list-row"}
              onClick={() => { setEditingService(service); setMessage(""); setFormError(""); }}
            >
              <div><strong>{service.name}</strong><span>{service.service_code}</span></div>
              <div><span>{service.average_service_time} min</span><StatusPill value={service.is_active ? "active" : "inactive"} /></div>
            </button>
          ))}
        </div>
      </section>
      <section className="surface">
        <SectionHeader
          eyebrow={editingService ? "Edit" : "Create"}
          title={editingService ? editingService.name : "New service"}
          action={editingService ? <button type="button" className="text-action" onClick={() => setEditingService(null)}>New service</button> : undefined}
        />
        <form key={editingService?.id || "new"} onSubmit={serviceSubmit}>
          <Field label="Service code"><input name="service_code" defaultValue={editingService?.service_code || ""} required /></Field>
          <Field label="Name"><input name="name" defaultValue={editingService?.name || ""} required /></Field>
          <Field label="Description"><textarea name="description" rows={4} defaultValue={editingService?.description || ""} /></Field>
          <Field label="Average service time (minutes)"><input name="average_service_time" type="number" min="1" defaultValue={editingService?.average_service_time || 15} required /></Field>
          <label className="check-field"><input name="is_active" type="checkbox" defaultChecked={editingService?.is_active ?? true} /><span>Active service</span></label>
          <button className="button button--primary" disabled={write.isPending}>{editingService ? "Update service" : "Create service"}</button>
        </form>
      </section>
    </div> : null}

    {tab === "capacity" ? <div className="admin-split">
      <section className="surface">
        <SectionHeader eyebrow="Availability" title="Branch services" />
        <div className="admin-list">
          {mappings.data?.map((mapping) => (
            <button
              type="button"
              key={mapping.id}
              className={editingMapping?.id === mapping.id ? "admin-list-row is-selected" : "admin-list-row"}
              onClick={() => { setEditingMapping(mapping); setMessage(""); setFormError(""); }}
            >
              <div><strong>{mapping.service_name}</strong><span>{mapping.branch_name || `Branch ${mapping.branch}`}</span></div>
              <div><span>{mapping.max_bookings_per_slot}/slot</span><StatusPill value={mapping.is_active ? "active" : "inactive"} /></div>
            </button>
          ))}
        </div>
      </section>
      <section className="surface">
        <SectionHeader
          eyebrow={editingMapping ? "Edit" : "Create"}
          title={editingMapping ? `${editingMapping.service_name} capacity` : "New branch service"}
          action={editingMapping ? <button type="button" className="text-action" onClick={() => setEditingMapping(null)}>New mapping</button> : undefined}
        />
        <form key={editingMapping?.id || "new"} onSubmit={mappingSubmit}>
          <Field label="Branch">
            <select name="branch" required disabled={Boolean(editingMapping)} defaultValue={editingMapping?.branch || ""}>
              <option value="">Select branch</option>
              {branches.data?.filter((branch) => branch.is_active || branch.id === editingMapping?.branch).map((branch) => <option key={branch.id} value={branch.id}>{branch.name}</option>)}
            </select>
          </Field>
          <Field label="Service">
            <select name="service" required disabled={Boolean(editingMapping)} defaultValue={editingMapping?.service || editingMapping?.service_id || ""}>
              <option value="">Select service</option>
              {services.data?.filter((service) => service.is_active || service.id === editingMapping?.service || service.id === editingMapping?.service_id).map((service) => <option key={service.id} value={service.id}>{service.name}</option>)}
            </select>
          </Field>
          <Field label="Bookings per slot"><input name="max_bookings_per_slot" type="number" min="1" defaultValue={editingMapping?.max_bookings_per_slot || 4} required /></Field>
          <label className="check-field"><input name="is_active" type="checkbox" defaultChecked={editingMapping?.is_active ?? true} /><span>Active mapping</span></label>
          <button className="button button--primary" disabled={write.isPending}>{editingMapping ? "Update mapping" : "Create mapping"}</button>
        </form>
      </section>
    </div> : null}

    {tab === "staff" ? <div className="admin-split">
      <section className="surface">
        <SectionHeader eyebrow="Access" title="Staff accounts" />
        <div className="admin-list">
          {staff.data?.map((person) => (
            <div className={editingStaff?.id === person.id ? "admin-list-row admin-list-row--static is-selected" : "admin-list-row admin-list-row--static"} key={person.id}>
              <button
                type="button"
                className="admin-record-button"
                onClick={() => { setEditingStaff(person); setStaffRole(person.role); setMessage(""); setFormError(""); }}
              >
                <strong>{person.first_name || person.username} {person.last_name}</strong>
                <span>{person.role.replaceAll("_", " ")} · {person.branch_name || "Global"}</span>
              </button>
              <div>
                <StatusPill value={person.is_active ? "active" : "inactive"} />
                {person.id === account.id ? <span className="muted">Current account</span> : <button type="button" className="text-action" onClick={() => activate.mutate({ id: person.id, is_active: !person.is_active })}>{person.is_active ? "Deactivate" : "Activate"}</button>}
              </div>
            </div>
          ))}
        </div>
      </section>
      <section className="surface">
        <SectionHeader
          eyebrow={editingStaff ? "Edit" : "Create"}
          title={editingStaff ? editingStaff.username : "New staff account"}
          action={editingStaff ? <button type="button" className="text-action" onClick={() => { setEditingStaff(null); setStaffRole("receptionist"); }}>New staff</button> : undefined}
        />
        <form key={editingStaff?.id || "new"} onSubmit={staffSubmit}>
          <div className="form-grid">
            <Field label="First name"><input name="first_name" defaultValue={editingStaff?.first_name || ""} required /></Field>
            <Field label="Last name"><input name="last_name" defaultValue={editingStaff?.last_name || ""} required /></Field>
            {!editingStaff ? <Field label="Username"><input name="username" required /></Field> : null}
            <Field label="Email"><input name="email" type="email" defaultValue={editingStaff?.email || ""} /></Field>
            {!editingStaff ? <Field label="Date of birth"><input name="date_of_birth" type="date" required /></Field> : null}
            {!editingStaff ? <Field label="Gender"><select name="gender" required defaultValue="other"><option value="other">Other</option><option value="female">Female</option><option value="male">Male</option></select></Field> : null}
            <Field label="Role">
              <select name="role" required value={staffRole} onChange={(event) => setStaffRole(event.target.value as StaffRole)}>
                {STAFF_ROLES.map((role) => <option key={role.value} value={role.value}>{role.label}</option>)}
              </select>
            </Field>
            <Field label="Branch">
              <select name="branch" disabled={staffRole === "system_admin"} required={staffRole !== "system_admin"} defaultValue={editingStaff?.branch_id || ""}>
                <option value="">{staffRole === "system_admin" ? "Global / none" : "Select branch"}</option>
                {branches.data?.filter((branch) => branch.is_active || branch.id === editingStaff?.branch_id).map((branch) => <option key={branch.id} value={branch.id}>{branch.name}</option>)}
              </select>
            </Field>
            {!editingStaff ? <Field label="Temporary password"><input name="password" type="password" autoComplete="new-password" required /></Field> : null}
            {!editingStaff ? <label className="check-field"><input name="disability_status" type="checkbox" /><span>Disability status</span></label> : null}
          </div>
          <button className="button button--primary" disabled={write.isPending}>{editingStaff ? "Update staff" : "Create staff account"}</button>
        </form>
      </section>
    </div> : null}

    {!branches.data?.length && tab === "branches" ? <EmptyState title="No branches configured" /> : null}
  </>;
}

export function AdminPage() {
  return <ProtectedWorkspace role="system_admin" title="Administration" subtitle="Manage branches, services, capacity and staff from one controlled console.">
    {(account) => <AdminBody account={account} />}
  </ProtectedWorkspace>;
}
