import React, { useCallback, useEffect, useState } from "react";
import SchoolOperations from "./school-operations";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  useWindowDimensions,
  View,
} from "react-native";

const API = process.env.EXPO_PUBLIC_API_URL || "http://127.0.0.1:8000";

type Admin = {
  id: number;
  full_name: string;
  email: string;
  school_id: number;
  role: string;
  is_active: boolean;
};

type School = {
  id: number;
  name: string;
  code: string;
  is_active: boolean;
  total_students: number;
  active_students: number;
};

type Student = {
  id: number;
  full_name: string;
  student_number: string;
  class_name: string | null;
  school_id: number;
  wallet_balance: number | null;
  currency: string | null;
  is_active: boolean;
};

type AuditEvent = {
  id: number;
  actor_id: number | null;
  school_id: number | null;
  action: string;
  entity_type: string;
  entity_id: number | null;
  outcome: string;
  created_at: string;
};

type Props = {
  fullName: string;
  role: string;
  accessToken: string;
  onSignOut: () => void;
};

export default function AdminDashboard({
  fullName,
  role,
  accessToken,
  onSignOut,
}: Props) {
  const { width } = useWindowDimensions();
  const wide = width >= 800;
  const isSystem = role === "system_admin";

  const [section, setSection] = useState("Overview");
  const [admins, setAdmins] = useState<Admin[]>([]);
  const [schools, setSchools] = useState<School[]>([]);
  const [students, setStudents] = useState<Student[]>([]);
  const [selectedSchool, setSelectedSchool] = useState<School | null>(null);
  const [schoolStudents, setSchoolStudents] = useState<Student[]>([]);
  const [schoolStudentTotal, setSchoolStudentTotal] = useState(0);
  const [schoolLoading, setSchoolLoading] = useState(false);
  const [moreLoading, setMoreLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [search, setSearch] = useState("");
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [auditSchool, setAuditSchool] = useState<number | null>(null);
  const [auditAction, setAuditAction] = useState("");
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditMoreAvailable, setAuditMoreAvailable] = useState(false);

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [schoolId, setSchoolId] = useState<number | null>(null);
  const [password, setPassword] = useState("");
  const [formError, setFormError] = useState("");

  const request = useCallback(
    async (path: string, method = "GET", payload?: object) => {
      const response = await fetch(`${API}${path}`, {
        method,
        headers: {
          Authorization: `Bearer ${accessToken}`,
          ...(payload ? { "Content-Type": "application/json" } : {}),
        },
        body: payload ? JSON.stringify(payload) : undefined,
      });

      if (!response.ok) {
        let detail = `Request failed (${response.status})`;
        try {
          const body = await response.json();
          if (typeof body.detail === "string") detail = body.detail;
        } catch {
          // Use the HTTP status message.
        }
        throw new Error(detail);
      }

      return response.json();
    },
    [accessToken]
  );

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      if (isSystem) {
        const [adminData, schoolData] = await Promise.all([
          request("/admin/school-admins"),
          request("/admin/school-directory"),
        ]);
        setAdmins(adminData);
        setSchools(schoolData);
        setStudents([]);
      } else {
        const studentData: Student[] = await request(
          "/admin/students?limit=100"
        );
        setStudents(studentData);
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load dashboard."
      );
    } finally {
      setLoading(false);
    }
  }, [isSystem, request]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function createAdmin() {
    if (
      !name.trim() ||
      !email.trim() ||
      schoolId === null ||
      password.length < 12
    ) {
      setFormError(
        "Please enter a full name, valid email, select a school, and provide a password of at least 12 characters."
      );
      return;
    }

    setBusy(true);
    setError("");
    setFormError("");
    setNotice("");

    try {
      await request("/admin/school-admins", "POST", {
        full_name: name.trim(),
        email: email.trim().toLowerCase(),
        school_id: schoolId,
        temporary_password: password,
      });

      setName("");
      setEmail("");
      setPassword("");
      setSchoolId(null);
      setNotice("School administrator account created.");
      setFormError("");

      await refresh();
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Account creation failed.";
      setError(message);
      setFormError(message);
    } finally {
      setBusy(false);
    }
  }

  async function deactivateAdmin(admin: Admin) {
    setBusy(true);
    setError("");
    setNotice("");

    try {
      await request(
        `/admin/school-admins/${admin.id}/deactivate`,
        "POST"
      );
      setNotice(`${admin.full_name}'s account was deactivated.`);
      await refresh();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Deactivation failed."
      );
    } finally {
      setBusy(false);
    }
  }

  const menu = isSystem
    ? ["Overview", "Schools", "School Administrators", "Audit Logs"]
    : ["Overview", "Students", "School Operations"];

  async function openSchool(school: School) {
    setSection("Schools");
    setSelectedSchool(school);
    setSchoolStudents([]);
    setSchoolStudentTotal(0);
    setSchoolLoading(true);
    setError("");

    try {
      const data = await request(
        `/admin/school-directory/${school.id}/students?limit=50&offset=0`
      );
      setSchoolStudents(data.students);
      setSchoolStudentTotal(data.total_students);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load students."
      );
    } finally {
      setSchoolLoading(false);
    }
  }

  async function loadMoreSchoolStudents() {
    if (!selectedSchool || moreLoading) return;

    setMoreLoading(true);
    setError("");
    try {
      const data = await request(
        `/admin/school-directory/${selectedSchool.id}/students?limit=50&offset=${schoolStudents.length}`
      );
      setSchoolStudents((previous) => [...previous, ...data.students]);
      setSchoolStudentTotal(data.total_students);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load more students."
      );
    } finally {
      setMoreLoading(false);
    }
  }

  const loadAudit = useCallback(
    async (offset = 0, append = false) => {
      if (!isSystem) return;

      setAuditLoading(true);
      setError("");

      try {
        const query = new URLSearchParams({
          limit: "50",
          offset: String(offset),
        });

        if (auditSchool !== null) {
          query.set("school_id", String(auditSchool));
        }

        if (auditAction.trim()) {
          query.set("action", auditAction.trim());
        }

        const data: AuditEvent[] = await request(
          `/audit/events?${query.toString()}`
        );

        setAuditEvents((previous) =>
          append ? [...previous, ...data] : data
        );
        setAuditMoreAvailable(data.length === 50);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to load audit logs."
        );
      } finally {
        setAuditLoading(false);
      }
    },
    [isSystem, request, auditSchool, auditAction]
  );

  useEffect(() => {
    if (section === "Audit Logs" && isSystem) {
      void loadAudit();
    }
  }, [section, isSystem, loadAudit]);

  const totalAcrossSchools = schools.reduce(
    (sum, school) => sum + school.total_students, 0
  );

  const filtered = students.filter((student) => {
    const q = search.trim().toLowerCase();
    return (
      student.full_name.toLowerCase().includes(q) ||
      student.student_number.toLowerCase().includes(q)
    );
  });

  const money = (student: Student) =>
    student.wallet_balance === null
      ? "No wallet"
      : `${student.currency ?? "UGX"} ${student.wallet_balance.toLocaleString("en-UG")}`;

  return (
    <View style={styles.page}>
      <View style={styles.header}>
        <View>
          <Text style={styles.logo}>SmartSpend</Text>
          <Text style={styles.small}>
            {isSystem ? "SYSTEM ADMINISTRATION" : "SCHOOL ADMINISTRATION"}
          </Text>
        </View>
        <Pressable
          style={styles.signOut}
          onPress={onSignOut}
          accessibilityRole="button"
        >
          <Text style={styles.link}>Sign out</Text>
        </Pressable>
      </View>

      <View style={[styles.body, wide && styles.bodyWide]}>
        <ScrollView
          horizontal={!wide}
          style={wide ? styles.sidebar : styles.mobileNav}
          contentContainerStyle={!wide ? styles.mobileNavContent : undefined}
        >
          {menu.map((item) => (
            <Pressable
              key={item}
              style={[
                styles.menuItem,
                section === item && styles.selectedMenu,
              ]}
              onPress={() => {
                setSection(item);
                if (item === "Schools") setSelectedSchool(null);
                setError("");
                setNotice("");
              }}
              accessibilityRole="button"
            >
              <Text
                style={[
                  styles.menuText,
                  section === item && styles.selectedMenuText,
                ]}
              >
                {item}
              </Text>
            </Pressable>
          ))}
        </ScrollView>

        <ScrollView
          style={styles.main}
          contentContainerStyle={styles.content}
          keyboardShouldPersistTaps="handled"
        >
          <Text style={styles.eyebrow}>ADMINISTRATION PORTAL</Text>
          <Text style={styles.heading}>
            {section === "Overview" ? `Welcome, ${fullName}` : section}
          </Text>

          {error !== "" && (
            <View style={styles.errorBox}>
              <Text style={styles.errorText}>{error}</Text>
            </View>
          )}
          {notice !== "" && (
            <View style={styles.successBox}>
              <Text style={styles.successText}>{notice}</Text>
            </View>
          )}

          {loading ? (
            <ActivityIndicator
              color="#14664D"
              size="large"
              style={{ marginTop: 36 }}
            />
          ) : (
            <>
              {section === "Overview" && (
                <>
                  <Text style={styles.description}>
                    {isSystem
                      ? "View student totals per school. Select a school to inspect individual student records."
                      : "Manage the students and cards assigned to your school."}
                  </Text>

                  <View style={[styles.stats, wide && styles.statsWide]}>
                    <View style={styles.greenCard}>
                      <Text style={styles.greenLabel}>
                        {isSystem ? "Total registered students" : "Students in loaded directory"}
                      </Text>
                      <Text style={styles.bigWhite}>
                        {isSystem ? totalAcrossSchools : students.length}
                      </Text>
                      <Text style={styles.greenLabel}>
                        {isSystem ? `Across ${schools.length} schools` : "First 100 authorized records"}
                      </Text>
                    </View>

                    {isSystem && (
                      <View style={styles.card}>
                        <Text style={styles.muted}>
                          Active school administrators
                        </Text>
                        <Text style={styles.bigGreen}>
                          {admins.filter((a) => a.is_active).length}
                        </Text>
                        <Text style={styles.muted}>
                          Across {schools.length} registered schools
                        </Text>
                      </View>
                    )}
                  </View>

                  <Pressable
                    style={styles.primaryButton}
                    onPress={() => setSection(
                      isSystem ? "Schools" : "Students"
                    )}
                  >
                    <Text style={styles.primaryButtonText}>
                      {isSystem
                        ? "View schools and student counts"
                        : "View school students"}
                    </Text>
                  </Pressable>
                </>
              )}

              {section === "School Administrators" && isSystem && (
                <>
                  <Text style={styles.description}>
                    Create school administrators, assign them to schools,
                    and deactivate accounts when necessary.
                  </Text>

                  <View style={styles.card}>
                    <Text style={styles.cardTitle}>
                      Create school administrator
                    </Text>

                    <Text style={styles.label}>Full name</Text>
                    <TextInput
                      style={styles.input}
                      value={name}
                      onChangeText={setName}
                      placeholder="Administrator's full name"
                      autoCapitalize="words"
                    />

                    <Text style={styles.label}>Email</Text>
                    <TextInput
                      style={styles.input}
                      value={email}
                      onChangeText={setEmail}
                      placeholder="admin@school.com"
                      keyboardType="email-address"
                      autoCapitalize="none"
                    />

                    <Text style={styles.label}>Assign to school</Text>
                    {schools.filter((s) => s.is_active).map((school) => (
                      <Pressable
                        key={school.id}
                        style={[
                          styles.schoolOption,
                          schoolId === school.id && styles.schoolSelected,
                        ]}
                        onPress={() => setSchoolId(school.id)}
                        accessibilityRole="radio"
                        accessibilityState={{
                          checked: schoolId === school.id,
                        }}
                      >
                        <Text style={styles.schoolOptionText}>
                          {school.name} ({school.code})
                        </Text>
                        {schoolId === school.id && (
                          <Text style={styles.link}>Selected</Text>
                        )}
                      </Pressable>
                    ))}

                    <Text style={styles.label}>
                      Temporary password
                    </Text>
                    <TextInput
                      style={styles.input}
                      value={password}
                      onChangeText={setPassword}
                      placeholder="At least 12 characters"
                      secureTextEntry
                      autoCapitalize="none"
                      autoCorrect={false}
                    />

                    <Text style={styles.muted}>
                      Development only: secure staff invitations and
                      mandatory password setup are still pending.
                    </Text>

                    {formError !== "" && (
                      <View style={styles.errorBox}>
                        <Text style={styles.errorText}>{formError}</Text>
                      </View>
                    )}

                    <Pressable
                      style={[
                        styles.primaryButton,
                        busy && styles.disabledButton,
                      ]}
                      disabled={busy}
                      onPress={() => void createAdmin()}
                    >
                      <Text style={styles.primaryButtonText}>
                        {busy ? "Processing..." : "Create administrator"}
                      </Text>
                    </Pressable>
                  </View>

                  <Text style={styles.cardTitle}>
                    Existing school administrators
                  </Text>

                  {admins.map((admin) => (
                    <View key={admin.id} style={styles.listRow}>
                      <View style={styles.rowContent}>
                        <Text style={styles.rowTitle}>
                          {admin.full_name}
                        </Text>
                        <Text style={styles.muted}>{admin.email}</Text>
                        <Text style={styles.muted}>
                          {schools.find((s) => s.id === admin.school_id)?.name ??
                            `School #${admin.school_id}`}
                        </Text>
                        <Text
                          style={
                            admin.is_active
                              ? styles.activeText
                              : styles.inactiveText
                          }
                        >
                          {admin.is_active ? "Active" : "Deactivated"}
                        </Text>
                      </View>

                      {admin.is_active && (
                        <Pressable
                          disabled={busy}
                          onPress={() => void deactivateAdmin(admin)}
                          style={styles.dangerButton}
                          accessibilityRole="button"
                        >
                          <Text style={styles.dangerText}>
                            Deactivate
                          </Text>
                        </Pressable>
                      )}
                    </View>
                  ))}
                </>
              )}

              {section === "Schools" && isSystem && (
                <>
                  {selectedSchool === null ? (
                    <>
                      <Text style={styles.description}>
                        Select a school to view its registered students.
                        Counts are calculated from the database.
                      </Text>

                      {schools.map((school) => (
                        <Pressable
                          key={school.id}
                          style={styles.listRow}
                          accessibilityRole="button"
                          onPress={() => void openSchool(school)}
                        >
                          <View style={styles.rowContent}>
                            <Text style={styles.rowTitle}>
                              {school.name}
                            </Text>
                            <Text style={styles.muted}>
                              {school.code} ? {school.is_active ? "Active school" : "Inactive school"}
                            </Text>
                            <Text style={styles.muted}>
                              {school.active_students} active students
                            </Text>
                          </View>
                          <View style={{ alignItems: "flex-end" }}>
                            <Text style={styles.bigGreen}>
                              {school.total_students}
                            </Text>
                            <Text style={styles.link}>
                              View students ?
                            </Text>
                          </View>
                        </Pressable>
                      ))}
                    </>
                  ) : (
                    <>
                      <Pressable
                        style={{ paddingVertical: 12 }}
                        onPress={() => setSelectedSchool(null)}
                      >
                        <Text style={styles.link}>? All schools</Text>
                      </Pressable>

                      <Text style={styles.cardTitle}>
                        {selectedSchool.name}
                      </Text>
                      <Text style={styles.description}>
                        {schoolStudentTotal} registered students
                        ? {selectedSchool.code}
                      </Text>

                      {schoolLoading ? (
                        <ActivityIndicator color="#14664D" />
                      ) : (
                        <>
                          {schoolStudents.map((student) => (
                            <View key={student.id} style={styles.listRow}>
                              <View style={styles.rowContent}>
                                <Text style={styles.rowTitle}>
                                  {student.full_name}
                                </Text>
                                <Text style={styles.muted}>
                                  {student.student_number} ? {student.class_name ?? "No class"}
                                </Text>
                                <Text style={styles.muted}>
                                  {student.is_active ? "Active" : "Inactive"}
                                </Text>
                              </View>
                              <Text style={styles.balance}>
                                {money(student)}
                              </Text>
                            </View>
                          ))}

                          {schoolStudents.length < schoolStudentTotal && (
                            <Pressable
                              style={styles.primaryButton}
                              disabled={moreLoading}
                              onPress={() => void loadMoreSchoolStudents()}
                            >
                              <Text style={styles.primaryButtonText}>
                                {moreLoading
                                  ? "Loading..."
                                  : `Load more (${schoolStudents.length} of ${schoolStudentTotal})`}
                              </Text>
                            </Pressable>
                          )}

                          {schoolStudentTotal === 0 && (
                            <Text style={styles.description}>
                              No students registered at this school.
                            </Text>
                          )}
                        </>
                      )}
                    </>
                  )}
                </>
              )}

              {section === "Audit Logs" && isSystem && (
                <>
                  <Text style={styles.description}>
                    Review administrative and security activity across
                    SmartSpend schools. Newest events appear first.
                  </Text>

                  <View style={styles.card}>
                    <Text style={styles.cardTitle}>Filter audit events</Text>

                    <Text style={styles.label}>School</Text>
                    <Pressable
                      style={styles.schoolOption}
                      onPress={() => setAuditSchool(null)}
                    >
                      <Text style={styles.schoolOptionText}>
                        All schools
                      </Text>
                      {auditSchool === null && (
                        <Text style={styles.link}>Selected</Text>
                      )}
                    </Pressable>

                    {schools.map((school) => (
                      <Pressable
                        key={school.id}
                        style={[
                          styles.schoolOption,
                          auditSchool === school.id &&
                            styles.schoolSelected,
                        ]}
                        onPress={() => setAuditSchool(school.id)}
                      >
                        <Text style={styles.schoolOptionText}>
                          {school.name}
                        </Text>
                        {auditSchool === school.id && (
                          <Text style={styles.link}>Selected</Text>
                        )}
                      </Pressable>
                    ))}

                    <Text style={styles.label}>Action</Text>
                    <TextInput
                      style={styles.input}
                      value={auditAction}
                      onChangeText={setAuditAction}
                      placeholder="e.g. card.blocked"
                      autoCapitalize="none"
                      autoCorrect={false}
                    />

                    <Pressable
                      style={styles.primaryButton}
                      disabled={auditLoading}
                      onPress={() => void loadAudit()}
                    >
                      <Text style={styles.primaryButtonText}>
                        {auditLoading ? "Loading..." : "Refresh audit logs"}
                      </Text>
                    </Pressable>
                  </View>

                  <Text style={styles.cardTitle}>Recent activity</Text>

                  {auditLoading && auditEvents.length === 0 && (
                    <ActivityIndicator color="#14664D" />
                  )}

                  {auditEvents.map((event) => {
                    const school = schools.find(
                      (s) => s.id === event.school_id
                    );

                    return (
                      <View key={event.id} style={styles.listRow}>
                        <View style={styles.rowContent}>
                          <Text style={styles.rowTitle}>
                            {event.action.replace(/\./g, " ? ")}
                          </Text>

                          <Text style={styles.muted}>
                            {school?.name ??
                              (event.school_id === null
                                ? "Platform-wide"
                                : `School #${event.school_id}`)}
                          </Text>

                          <Text style={styles.muted}>
                            Actor: {event.actor_id === null
                              ? "System"
                              : `User #${event.actor_id}`}
                          </Text>

                          <Text style={styles.muted}>
                            {event.entity_type} #{event.entity_id ?? "N/A"}
                          </Text>

                          <Text style={styles.muted}>
                            {new Date(event.created_at).toLocaleString()}
                          </Text>

                          <Text
                            style={
                              event.outcome === "success"
                                ? styles.activeText
                                : styles.inactiveText
                            }
                          >
                            {event.outcome.toUpperCase()}
                          </Text>
                        </View>
                      </View>
                    );
                  })}

                  {!auditLoading && auditEvents.length === 0 && (
                    <Text style={styles.description}>
                      No audit events match the selected filters.
                    </Text>
                  )}

                  {auditMoreAvailable && (
                    <Pressable
                      style={styles.primaryButton}
                      disabled={auditLoading}
                      onPress={() =>
                        void loadAudit(auditEvents.length, true)
                      }
                    >
                      <Text style={styles.primaryButtonText}>
                        {auditLoading
                          ? "Loading..."
                          : "Load more audit events"}
                      </Text>
                    </Pressable>
                  )}
                </>
              )}

              {section === "School Operations" && !isSystem && (
                <SchoolOperations accessToken={accessToken} />
              )}

              {section === "Students" && (
                <>
                  <Text style={styles.description}>
                    Search student accounts and view wallet balances
                    within your authorized schools.
                  </Text>

                  <TextInput
                    style={styles.input}
                    value={search}
                    onChangeText={setSearch}
                    placeholder="Search name or student number"
                  />

                  <Text style={styles.muted}>
                    Showing up to 100 records. Server-side search and
                    pagination will be added next.
                  </Text>

                  {filtered.map((student) => (
                    <View key={student.id} style={styles.listRow}>
                      <View style={styles.rowContent}>
                        <Text style={styles.rowTitle}>
                          {student.full_name}
                        </Text>
                        <Text style={styles.muted}>
                          {student.student_number} · {student.class_name ?? "No class"}
                        </Text>
                        <Text style={styles.muted}>
                          School #{student.school_id}
                        </Text>
                      </View>
                      <Text style={styles.balance}>
                        {money(student)}
                      </Text>
                    </View>
                  ))}

                  {filtered.length === 0 && (
                    <Text style={styles.description}>
                      No matching students in the loaded records.
                    </Text>
                  )}
                </>
              )}
            </>
          )}

          <Pressable
            onPress={() => void refresh()}
            style={styles.refreshButton}
          >
            <Text style={styles.link}>Refresh dashboard data</Text>
          </Pressable>
        </ScrollView>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: "#F7FAF8" },
  header: {
    backgroundColor: "#FFFFFF",
    paddingHorizontal: 24,
    paddingVertical: 18,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    borderBottomWidth: 1,
    borderBottomColor: "#DFEAE4",
  },
  logo: { color: "#14664D", fontSize: 24, fontWeight: "800" },
  small: { color: "#647A76", fontSize: 10, letterSpacing: 1 },
  signOut: {
    backgroundColor: "#EDF5F0",
    padding: 12,
    borderRadius: 10,
  },
  link: { color: "#14664D", fontWeight: "700" },
  body: { flex: 1 },
  bodyWide: { flexDirection: "row" },
  sidebar: {
    width: 225,
    flexGrow: 0,
    backgroundColor: "#FFFFFF",
    padding: 12,
    borderRightWidth: 1,
    borderRightColor: "#DFEAE4",
  },
  mobileNav: { maxHeight: 65, flexGrow: 0, backgroundColor: "#FFFFFF" },
  mobileNavContent: { alignItems: "center", paddingHorizontal: 8 },
  menuItem: { padding: 14, borderRadius: 10, marginVertical: 3 },
  selectedMenu: { backgroundColor: "#EDF5F0" },
  menuText: { color: "#647A76", fontWeight: "600" },
  selectedMenuText: { color: "#14664D", fontWeight: "800" },
  main: { flex: 1 },
  content: {
    width: "100%",
    maxWidth: 1100,
    alignSelf: "center",
    padding: 24,
    paddingBottom: 70,
  },
  eyebrow: {
    color: "#14664D",
    fontSize: 11,
    fontWeight: "800",
    letterSpacing: 1.5,
  },
  heading: {
    fontSize: 29,
    fontWeight: "800",
    color: "#173445",
    marginTop: 9,
  },
  description: {
    color: "#647A76",
    fontSize: 14,
    lineHeight: 22,
    marginVertical: 20,
  },
  stats: { gap: 15 },
  statsWide: { flexDirection: "row" },
  greenCard: {
    flex: 1,
    backgroundColor: "#14664D",
    padding: 26,
    borderRadius: 18,
  },
  greenLabel: { color: "#D4EADF", fontSize: 13 },
  bigWhite: {
    color: "#FFFFFF",
    fontSize: 37,
    fontWeight: "800",
    marginVertical: 16,
  },
  card: {
    flex: 1,
    backgroundColor: "#FFFFFF",
    padding: 24,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: "#DFEAE4",
    marginTop: 20,
  },
  bigGreen: {
    color: "#14664D",
    fontSize: 37,
    fontWeight: "800",
    marginVertical: 16,
  },
  muted: { color: "#647A76", fontSize: 12, lineHeight: 20 },
  cardTitle: {
    color: "#173445",
    fontSize: 19,
    fontWeight: "800",
    marginBottom: 16,
    marginTop: 15,
  },
  label: {
    color: "#173445",
    fontSize: 13,
    fontWeight: "700",
    marginTop: 17,
    marginBottom: 8,
  },
  input: {
    backgroundColor: "#FBFDFC",
    borderWidth: 1,
    borderColor: "#DFEAE4",
    borderRadius: 11,
    padding: 14,
    color: "#173445",
    fontSize: 14,
  },
  schoolOption: {
    padding: 14,
    backgroundColor: "#F7FAF8",
    borderRadius: 11,
    marginBottom: 8,
    flexDirection: "row",
    justifyContent: "space-between",
  },
  schoolSelected: {
    borderWidth: 1,
    borderColor: "#14664D",
    backgroundColor: "#EDF5F0",
  },
  schoolOptionText: { color: "#173445", flex: 1 },
  primaryButton: {
    backgroundColor: "#14664D",
    borderRadius: 12,
    padding: 16,
    alignItems: "center",
    marginTop: 22,
  },
  disabledButton: { opacity: 0.5 },
  primaryButtonText: { color: "#FFFFFF", fontWeight: "800" },
  listRow: {
    padding: 18,
    borderRadius: 14,
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: "#DFEAE4",
    marginTop: 11,
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  rowContent: { flex: 1 },
  rowTitle: {
    color: "#173445",
    fontSize: 15,
    fontWeight: "800",
    marginBottom: 5,
  },
  balance: { color: "#14664D", fontWeight: "800" },
  activeText: { color: "#14664D", marginTop: 6 },
  inactiveText: { color: "#AA372F", marginTop: 6 },
  dangerButton: {
    backgroundColor: "#FFF0EE",
    padding: 11,
    borderRadius: 10,
  },
  dangerText: { color: "#AA372F", fontWeight: "700" },
  errorBox: {
    backgroundColor: "#FFF0EE",
    padding: 14,
    borderRadius: 11,
    marginTop: 18,
  },
  errorText: { color: "#AA372F" },
  successBox: {
    backgroundColor: "#EDF5F0",
    padding: 14,
    borderRadius: 11,
    marginTop: 18,
  },
  successText: { color: "#14664D" },
  refreshButton: { paddingVertical: 24, alignItems: "center" },
});
