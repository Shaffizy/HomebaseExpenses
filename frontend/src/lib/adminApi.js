import { api } from "./api";
export async function registerUser(payload) {
    const { data } = await api.post("/auth/register", payload);
    return data;
}
export async function listUsers(organizationId) {
    const { data } = await api.get(`/organizations/${organizationId}/users/`);
    if (Array.isArray(data))
        return data;
    return data.results ?? [];
}
export async function updateUser(organizationId, userId, patch) {
    const { data } = await api.patch(`/organizations/${organizationId}/users/${userId}/`, patch);
    return data;
}
export async function deleteUser(organizationId, userId) {
    await api.delete(`/organizations/${organizationId}/users/${userId}/delete/`);
}
export async function getOrgSettings() {
    const { data } = await api.get("/organizations/me/settings/");
    return data;
}
export async function updateOrgSettings(patch) {
    const { data } = await api.patch("/organizations/me/settings/", patch);
    return data;
}
