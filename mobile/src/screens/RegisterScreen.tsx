import { useState } from "react";
import { ActivityIndicator, Alert, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";

import { useAuth } from "../auth/AuthContext";
import { ApiError } from "../api/client";
import type { AuthStackParamList } from "../navigation/AuthStack";

type Props = NativeStackScreenProps<AuthStackParamList, "Register">;

export default function RegisterScreen({ navigation }: Props) {
  const { register } = useAuth();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit() {
    if (password.length < 8) {
      Alert.alert("Contraseña demasiado corta", "Mínimo 8 caracteres.");
      return;
    }
    setIsSubmitting(true);
    try {
      await register(email.trim(), password, fullName.trim() || undefined);
    } catch (err) {
      const message = err instanceof ApiError ? err.detail : "No se pudo crear la cuenta";
      Alert.alert("Error", message);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Crear cuenta</Text>

      <Text style={styles.label}>Nombre (opcional)</Text>
      <TextInput style={styles.input} placeholder="Ej. Luis" value={fullName} onChangeText={setFullName} />

      <Text style={styles.label}>Email</Text>
      <TextInput
        style={styles.input}
        placeholder="tucorreo@ejemplo.com"
        autoCapitalize="none"
        keyboardType="email-address"
        value={email}
        onChangeText={setEmail}
      />

      <Text style={styles.label}>Contraseña</Text>
      <TextInput
        style={styles.input}
        placeholder="Mínimo 8 caracteres"
        secureTextEntry
        value={password}
        onChangeText={setPassword}
      />

      <Pressable
        style={[styles.button, isSubmitting && styles.buttonDisabled]}
        onPress={handleSubmit}
        disabled={isSubmitting || !email || !password}
      >
        {isSubmitting ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>Registrarme</Text>}
      </Pressable>

      <Pressable onPress={() => navigation.navigate("Login")}>
        <Text style={styles.link}>¿Ya tienes cuenta? Inicia sesión</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: "center", padding: 24, backgroundColor: "#fff" },
  title: { fontSize: 26, fontWeight: "700", textAlign: "center", marginBottom: 32 },
  label: { fontSize: 13, fontWeight: "600", color: "#444", marginBottom: 6 },
  input: {
    borderWidth: 1,
    borderColor: "#ccc",
    borderRadius: 8,
    padding: 12,
    marginBottom: 12,
    fontSize: 16,
  },
  button: {
    backgroundColor: "#2e7d32",
    borderRadius: 8,
    padding: 14,
    alignItems: "center",
    marginTop: 8,
  },
  buttonDisabled: { opacity: 0.6 },
  buttonText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  link: { color: "#2e7d32", textAlign: "center", marginTop: 20 },
});
