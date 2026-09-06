import { useEffect, useState } from "react";
import { ActivityIndicator, Alert, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";

import { useAuth } from "../auth/AuthContext";
import { changePassword } from "../api/auth";
import { ApiError } from "../api/client";
import { getApiBaseUrl, setApiBaseUrl } from "../auth/secureStorage";
import { DEFAULT_API_BASE_URL } from "../config";

export default function ProfileScreen() {
  const { user, logout } = useAuth();

  const [serverUrl, setServerUrl] = useState(DEFAULT_API_BASE_URL);
  const [savedServerUrl, setSavedServerUrl] = useState(DEFAULT_API_BASE_URL);

  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [isChangingPassword, setIsChangingPassword] = useState(false);

  useEffect(() => {
    getApiBaseUrl().then((url) => {
      setServerUrl(url);
      setSavedServerUrl(url);
    });
  }, []);

  async function handleSaveServerUrl() {
    await setApiBaseUrl(serverUrl.trim());
    setSavedServerUrl(serverUrl.trim());
    Alert.alert(
      "Guardado",
      "La app hablará con esa URL a partir de ahora. Si cambia el servidor conviene cerrar sesión y volver a entrar."
    );
  }

  async function handleChangePassword() {
    if (newPassword.length < 8) {
      Alert.alert("Contraseña demasiado corta", "Mínimo 8 caracteres.");
      return;
    }
    setIsChangingPassword(true);
    try {
      await changePassword(oldPassword, newPassword);
      setOldPassword("");
      setNewPassword("");
      Alert.alert("Listo", "Contraseña actualizada. Se han cerrado el resto de tus sesiones.");
    } catch (err) {
      const message = err instanceof ApiError ? err.detail : "No se pudo cambiar la contraseña";
      Alert.alert("Error", message);
    } finally {
      setIsChangingPassword(false);
    }
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.email}>{user?.email}</Text>
      {user?.full_name ? <Text style={styles.name}>{user.full_name}</Text> : null}

      <Text style={styles.sectionTitle}>Cambiar contraseña</Text>
      <Text style={styles.label}>Contraseña actual</Text>
      <TextInput
        style={styles.input}
        placeholder="Tu contraseña actual"
        secureTextEntry
        value={oldPassword}
        onChangeText={setOldPassword}
      />
      <Text style={styles.label}>Contraseña nueva</Text>
      <TextInput
        style={styles.input}
        placeholder="Mínimo 8 caracteres"
        secureTextEntry
        value={newPassword}
        onChangeText={setNewPassword}
      />
      <Pressable
        style={[styles.secondaryButton, (!oldPassword || !newPassword) && styles.buttonDisabled]}
        disabled={!oldPassword || !newPassword || isChangingPassword}
        onPress={handleChangePassword}
      >
        {isChangingPassword ? (
          <ActivityIndicator color="#2e7d32" />
        ) : (
          <Text style={styles.secondaryButtonText}>Actualizar contraseña</Text>
        )}
      </Pressable>

      <Text style={styles.sectionTitle}>URL del servidor</Text>
      <Text style={styles.hint}>
        Por defecto apunta a la Pi por tu WiFi de casa. Cámbiala aquí si usas una URL de Cloudflare Tunnel para
        acceder desde fuera.
      </Text>
      <Text style={styles.label}>Dirección del servidor</Text>
      <TextInput
        style={styles.input}
        placeholder="https://..."
        autoCapitalize="none"
        autoCorrect={false}
        value={serverUrl}
        onChangeText={setServerUrl}
      />
      <Pressable
        style={[styles.secondaryButton, serverUrl === savedServerUrl && styles.buttonDisabled]}
        disabled={serverUrl === savedServerUrl}
        onPress={handleSaveServerUrl}
      >
        <Text style={styles.secondaryButtonText}>Guardar URL</Text>
      </Pressable>

      <Pressable style={styles.logoutButton} onPress={() => logout()}>
        <Text style={styles.logoutButtonText}>Cerrar sesión</Text>
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#fff" },
  content: { padding: 24, paddingBottom: 60 },
  email: { fontSize: 18, fontWeight: "600" },
  name: { fontSize: 14, color: "#666", marginTop: 4 },
  sectionTitle: { fontSize: 15, fontWeight: "700", marginTop: 28, marginBottom: 8, color: "#333" },
  hint: { fontSize: 13, color: "#888", marginBottom: 10, lineHeight: 18 },
  label: { fontSize: 13, fontWeight: "600", color: "#444", marginBottom: 6 },
  input: { borderWidth: 1, borderColor: "#ccc", borderRadius: 8, padding: 12, marginBottom: 10, fontSize: 15 },
  secondaryButton: {
    borderWidth: 1,
    borderColor: "#2e7d32",
    borderRadius: 8,
    padding: 12,
    alignItems: "center",
  },
  secondaryButtonText: { color: "#2e7d32", fontWeight: "600", fontSize: 15 },
  buttonDisabled: { opacity: 0.4 },
  logoutButton: {
    backgroundColor: "#c62828",
    borderRadius: 8,
    padding: 14,
    alignItems: "center",
    marginTop: 40,
  },
  logoutButtonText: { color: "#fff", fontSize: 16, fontWeight: "600" },
});
