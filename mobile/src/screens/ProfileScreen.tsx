import { Pressable, StyleSheet, Text, View } from "react-native";

import { useAuth } from "../auth/AuthContext";

export default function ProfileScreen() {
  const { user, logout } = useAuth();

  return (
    <View style={styles.container}>
      <Text style={styles.email}>{user?.email}</Text>
      {user?.full_name ? <Text style={styles.name}>{user.full_name}</Text> : null}

      <Pressable style={styles.button} onPress={() => logout()}>
        <Text style={styles.buttonText}>Cerrar sesión</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 24, paddingTop: 60, backgroundColor: "#fff" },
  email: { fontSize: 18, fontWeight: "600" },
  name: { fontSize: 14, color: "#666", marginTop: 4 },
  button: {
    backgroundColor: "#c62828",
    borderRadius: 8,
    padding: 14,
    alignItems: "center",
    marginTop: 32,
  },
  buttonText: { color: "#fff", fontSize: 16, fontWeight: "600" },
});
