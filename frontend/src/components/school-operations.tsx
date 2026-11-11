import React, { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

const API =
  process.env.EXPO_PUBLIC_API_URL || "http://127.0.0.1:8000";

type Props = {
  accessToken: string;
};

type CurrentUser = {
  id: number;
  full_name: string;
  role: string;
  school_id: number | null;
};

type Student = {
  id: number;
  full_name: string;
  student_number: string;
  class_name: string | null;
  wallet_balance: number | null;
  currency: string | null;
};

type Card = {
  id: number;
  student_id: number;
  status: string;
  issued_at: string;
};

type RegistrationResult = {
  id: number;
  parent_id: number;
  wallet_id: number;
};

export default function SchoolOperations({ accessToken }: Props) {
  const [schoolId, setSchoolId] = useState<number | null>(null);
  const [tab, setTab] = useState<"enrollment" | "cards">("enrollment");
  const [students, setStudents] = useState<Student[]>([]);
  const [selectedStudent, setSelectedStudent] = useState<Student | null>(null);
  const [cards, setCards] = useState<Card[]>([]);

  const [studentName, setStudentName] = useState("");
  const [studentNumber, setStudentNumber] = useState("");
  const [className, setClassName] = useState("");
  const [parentMode, setParentMode] = useState<"new" | "existing">("new");
  const [parentName, setParentName] = useState("");
  const [parentEmail, setParentEmail] = useState("");
  const [parentPhone, setParentPhone] = useState("");
  const [parentId, setParentId] = useState("");

  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [pendingAction, setPendingAction] = useState<string | null>(null);

  const request = useCallback(
    async (path: string, method = "GET", body?: object) => {
      const response = await fetch(`${API}${path}`, {
        method,
        headers: {
          Authorization: `Bearer ${accessToken}`,
          ...(body ? { "Content-Type": "application/json" } : {}),
        },
        body: body ? JSON.stringify(body) : undefined,
      });

      const result = await response.json().catch(() => null);

      if (!response.ok) {
        let message = `HTTP ${response.status}`;
        if (typeof result?.detail === "string") {
          message = result.detail;
        } else if (Array.isArray(result?.detail)) {
          message = result.detail
            .map((item: { msg?: string; loc?: string[] }) =>
              `${item.loc?.join(".") ?? "Field"}: ${item.msg ?? "Invalid"}`
            )
            .join("; ");
        }
        throw new Error(message);
      }

      return result;
    },
    [accessToken]
  );

  const loadStudents = useCallback(async () => {
    const data: Student[] = await request("/admin/students?limit=100");
    setStudents(data);
  }, [request]);

  useEffect(() => {
    let active = true;

    async function initialize() {
      setLoading(true);
      try {
        const user: CurrentUser = await request("/auth/me");
        if (user.role !== "school_admin" || user.school_id === null) {
          throw new Error("This account has no assigned school.");
        }

        if (!active) return;
        setSchoolId(user.school_id);
        await loadStudents();
      } catch (err) {
        if (active) {
          setError(err instanceof Error ? err.message : "Unable to load school.");
        }
      } finally {
        if (active) setLoading(false);
      }
    }

    void initialize();
    return () => {
      active = false;
    };
  }, [request, loadStudents]);

  async function registerStudent() {
    setError("");
    setSuccess("");

    if (
      schoolId === null ||
      !studentName.trim() ||
      !studentNumber.trim()
    ) {
      setError("Student name and student number are required.");
      return;
    }

    let parent: object;

    if (parentMode === "new") {
      if (!parentName.trim() || !parentEmail.trim()) {
        setError("New parent name and email are required.");
        return;
      }

      parent = {
        new_parent: {
          full_name: parentName.trim(),
          email: parentEmail.trim().toLowerCase(),
          phone: parentPhone.trim() || null,
        },
      };
    } else {
      const id = Number(parentId);

      if (!Number.isSafeInteger(id) || id <= 0) {
        setError("Enter a valid existing parent account ID.");
        return;
      }

      parent = { parent_id: id };
    }

    setBusy(true);

    try {
      const result: RegistrationResult = await request(
        "/students",
        "POST",
        {
          full_name: studentName.trim(),
          student_number: studentNumber.trim(),
          class_name: className.trim() || null,
          school_id: schoolId,
          ...parent,
        }
      );

      setSuccess(
        `Student registered successfully. Student ID: ${result.id}. ` +
        `Linked parent ID: ${result.parent_id}. Wallet ID: ${result.wallet_id}.`
      );

      setStudentName("");
      setStudentNumber("");
      setClassName("");
      setParentName("");
      setParentEmail("");
      setParentPhone("");
      setParentId("");

      await loadStudents();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Student registration failed."
      );
    } finally {
      setBusy(false);
    }
  }

  async function openStudent(student: Student) {
    setSelectedStudent(student);
    setCards([]);
    setPendingAction(null);
    setError("");
    setSuccess("");
    setBusy(true);

    try {
      const result: Card[] = await request(`/cards/student/${student.id}`);
      setCards(result);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Unable to load cards."
      );
    } finally {
      setBusy(false);
    }
  }

  async function performCardAction(
    operation: "issue" | "block" | "replace",
    cardId?: number
  ) {
    if (!selectedStudent || busy) return;

    setBusy(true);
    setError("");
    setSuccess("");

    try {
      if (operation === "issue") {
        await request("/cards/issue", "POST", {
          student_id: selectedStudent.id,
        });
      } else {
        await request(`/cards/${cardId}/${operation}`, "POST");
      }

      const updated: Card[] = await request(
        `/cards/student/${selectedStudent.id}`
      );
      setCards(updated);
      setSuccess(`Card ${operation} operation completed successfully.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Card operation failed.");
    } finally {
      setPendingAction(null);
      setBusy(false);
    }
  }

  const Button = ({
    label,
    onPress,
    danger = false,
    disabled = false,
  }: {
    label: string;
    onPress: () => void;
    danger?: boolean;
    disabled?: boolean;
  }) => (
    <Pressable
      onPress={onPress}
      disabled={disabled || busy}
      style={[
        styles.button,
        danger && styles.danger,
        (disabled || busy) && styles.disabled,
      ]}
      accessibilityRole="button"
    >
      <Text style={styles.buttonText}>{label}</Text>
    </Pressable>
  );

  if (loading) {
    return <ActivityIndicator color="#14664D" style={{ marginTop: 25 }} />;
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>School Operations</Text>
      <Text style={styles.subtitle}>
        Assigned school ID: {schoolId ?? "Not assigned"}
      </Text>

      <View style={styles.tabs}>
        <Pressable onPress={() => setTab("enrollment")} style={styles.tab}>
          <Text style={tab === "enrollment" ? styles.selected : styles.muted}>
            Register Student
          </Text>
        </Pressable>
        <Pressable onPress={() => setTab("cards")} style={styles.tab}>
          <Text style={tab === "cards" ? styles.selected : styles.muted}>
            Manage Cards
          </Text>
        </Pressable>
      </View>

      {error !== "" && (
        <View style={styles.errorBox}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      )}

      {success !== "" && (
        <View style={styles.successBox}>
          <Text style={styles.successText}>{success}</Text>
        </View>
      )}

      {tab === "enrollment" && (
        <View style={styles.panel}>
          <Text style={styles.heading}>Student information</Text>
          <TextInput
            style={styles.input}
            placeholder="Full name"
            value={studentName}
            onChangeText={setStudentName}
          />
          <TextInput
            style={styles.input}
            placeholder="Student number"
            value={studentNumber}
            onChangeText={setStudentNumber}
          />
          <TextInput
            style={styles.input}
            placeholder="Class (optional)"
            value={className}
            onChangeText={setClassName}
          />

          <Text style={styles.heading}>Parent information</Text>
          <View style={styles.tabs}>
            <Pressable
              style={styles.tab}
              onPress={() => setParentMode("new")}
            >
              <Text style={parentMode === "new" ? styles.selected : styles.muted}>
                New Parent
              </Text>
            </Pressable>
            <Pressable
              style={styles.tab}
              onPress={() => setParentMode("existing")}
            >
              <Text style={parentMode === "existing" ? styles.selected : styles.muted}>
                Existing Parent
              </Text>
            </Pressable>
          </View>

          {parentMode === "new" ? (
            <>
              <TextInput
                style={styles.input}
                placeholder="Parent full name"
                value={parentName}
                onChangeText={setParentName}
              />
              <TextInput
                style={styles.input}
                placeholder="Parent email"
                keyboardType="email-address"
                autoCapitalize="none"
                value={parentEmail}
                onChangeText={setParentEmail}
              />
              <TextInput
                style={styles.input}
                placeholder="Parent phone (optional)"
                keyboardType="phone-pad"
                value={parentPhone}
                onChangeText={setParentPhone}
              />
              <Text style={styles.note}>
                New parents will require a secure account-activation process
                before they can sign in.
              </Text>
            </>
          ) : (
            <>
              <TextInput
                style={styles.input}
                placeholder="Verified existing parent ID"
                keyboardType="number-pad"
                value={parentId}
                onChangeText={setParentId}
              />
              <Text style={styles.note}>
                Only link an existing account after verifying the parent's
                identity and relationship to the student.
              </Text>
            </>
          )}

          <Button
            label={busy ? "Registering..." : "Register Student & Link Parent"}
            onPress={() => void registerStudent()}
          />
        </View>
      )}

      {tab === "cards" && (
        <>
          <Text style={styles.heading}>Select a student</Text>
          <Text style={styles.note}>
            Showing the first 100 authorized student records.
          </Text>

          <Button
            label="Refresh student list"
            onPress={() => void loadStudents().catch((err) =>
              setError(err instanceof Error ? err.message : "Refresh failed.")
            )}
          />

          <ScrollView style={styles.studentList} nestedScrollEnabled>
            {students.map((student) => (
              <Pressable
                key={student.id}
                style={[
                  styles.studentRow,
                  selectedStudent?.id === student.id && styles.activeRow,
                ]}
                onPress={() => void openStudent(student)}
              >
                <Text style={styles.studentName}>{student.full_name}</Text>
                <Text style={styles.muted}>
                  {student.student_number} · {student.class_name ?? "No class"}
                </Text>
              </Pressable>
            ))}
          </ScrollView>

          {selectedStudent && (
            <View style={styles.panel}>
              <Text style={styles.heading}>{selectedStudent.full_name}</Text>
              <Text style={styles.note}>
                Wallet: {selectedStudent.currency ?? "UGX"}{" "}
                {selectedStudent.wallet_balance?.toLocaleString("en-UG") ?? "N/A"}
              </Text>

              {cards.length === 0 && (
                <Text style={styles.note}>No cards found.</Text>
              )}

              {!cards.some((card) => card.status === "active") && (
                <Button
                  label="Issue New Card"
                  onPress={() => void performCardAction("issue")}
                />
              )}

              {cards.map((card) => (
                <View key={card.id} style={styles.cardRow}>
                  <Text style={styles.studentName}>Card #{card.id}</Text>
                  <Text style={styles.note}>Status: {card.status}</Text>

                  {card.status === "active" && (
                    <Button
                      label="Block Card"
                      danger
                      onPress={() => setPendingAction(`block:${card.id}`)}
                    />
                  )}

                  {["active", "blocked", "lost"].includes(card.status) && (
                    <Button
                      label="Replace Card"
                      onPress={() => setPendingAction(`replace:${card.id}`)}
                    />
                  )}

                  {pendingAction && pendingAction.endsWith(`:${card.id}`) && (
                    <View style={styles.confirmBox}>
                      <Text style={styles.note}>
                        Confirm {pendingAction.split(":")[0]} for card #{card.id}?
                      </Text>
                      <Button
                        label="Confirm action"
                        danger
                        onPress={() => {
                          const [operation] = pendingAction.split(":");
                          void performCardAction(
                            operation as "block" | "replace",
                            card.id
                          );
                        }}
                      />
                      <Pressable onPress={() => setPendingAction(null)}>
                        <Text style={styles.cancel}>Cancel</Text>
                      </Pressable>
                    </View>
                  )}
                </View>
              ))}
            </View>
          )}
        </>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { paddingVertical: 12, gap: 12 },
  title: { fontSize: 25, fontWeight: "800", color: "#173445" },
  subtitle: { fontSize: 13, color: "#647A76" },
  heading: {
    fontSize: 18,
    fontWeight: "700",
    color: "#173445",
    marginVertical: 12,
  },
  tabs: { flexDirection: "row", gap: 12, marginVertical: 12 },
  tab: {
    padding: 12,
    borderRadius: 10,
    backgroundColor: "#EAF2ED",
  },
  selected: { color: "#14664D", fontWeight: "800" },
  muted: { color: "#647A76", fontSize: 12 },
  panel: {
    backgroundColor: "#FFFFFF",
    padding: 18,
    borderRadius: 15,
    borderWidth: 1,
    borderColor: "#DFEAE4",
    gap: 8,
  },
  input: {
    borderWidth: 1,
    borderColor: "#DFEAE4",
    borderRadius: 10,
    padding: 13,
    backgroundColor: "#FBFDFC",
    color: "#173445",
  },
  note: { color: "#647A76", fontSize: 12, lineHeight: 19 },
  button: {
    backgroundColor: "#14664D",
    padding: 14,
    borderRadius: 10,
    alignItems: "center",
    marginTop: 9,
  },
  danger: { backgroundColor: "#A52F2F" },
  disabled: { opacity: 0.5 },
  buttonText: { color: "#FFFFFF", fontWeight: "800" },
  studentList: { maxHeight: 300 },
  studentRow: {
    padding: 14,
    borderBottomWidth: 1,
    borderColor: "#DFEAE4",
  },
  activeRow: { backgroundColor: "#EAF2ED" },
  studentName: { color: "#173445", fontWeight: "700" },
  cardRow: {
    borderTopWidth: 1,
    borderColor: "#DFEAE4",
    paddingVertical: 12,
    gap: 6,
  },
  confirmBox: {
    padding: 12,
    backgroundColor: "#FFF2F0",
    borderRadius: 10,
  },
  cancel: {
    textAlign: "center",
    color: "#647A76",
    padding: 12,
  },
  errorBox: {
    backgroundColor: "#FFF0EE",
    borderRadius: 10,
    padding: 12,
  },
  errorText: { color: "#A52F2F" },
  successBox: {
    backgroundColor: "#EAF2ED",
    borderRadius: 10,
    padding: 12,
  },
  successText: { color: "#14664D" },
});
