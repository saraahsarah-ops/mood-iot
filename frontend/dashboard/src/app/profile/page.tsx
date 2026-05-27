"use client";

import { useState, useEffect } from "react";
import { useAuthStore } from "@/lib/auth";
import { getDoctorProfile, updateDoctorProfile } from "@/lib/api";

interface DoctorData {
  user_id: string;
  email: string;
  first_name: string;
  last_name: string;
  speciality: string | null;
  rpps_number: string | null;
  license_number: string | null;
  institution_name: string | null;
  registration_status: string;
  created_at: string;
}

export default function ProfilePage() {
  const user = useAuthStore((s) => s.user);
  const [profile, setProfile] = useState<DoctorData | null>(null);
  const [loading, setLoading] = useState(true);
  
  // Edit mode fields
  const [editFirst, setEditFirst] = useState("");
  const [editLast, setEditLast] = useState("");
  const [editEmail, setEditEmail] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<{ type: "success" | "error", text: string } | null>(null);

  // Password fields
  const [changePassword, setChangePassword] = useState(false);
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const data = await getDoctorProfile();
        setProfile(data);
      } catch (err) {
        console.error("Profile load error", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [user]);

  useEffect(() => {
    if (profile) {
      setEditFirst(profile.first_name || user?.first_name || "");
      setEditLast(profile.last_name || user?.last_name || "");
      setEditEmail(profile.email || user?.email || "");
    }
  }, [profile, user]);

  async function handleSave() {
    setSaving(true);
    setSaveMsg(null);
    try {
      const updated = await updateDoctorProfile({
        first_name: editFirst,
        last_name: editLast,
      });
      setProfile((prev) => (prev ? { ...prev, ...updated } : prev));
      setSaveMsg({ type: "success", text: "Profil mis a jour avec succes." });
      setTimeout(() => setSaveMsg(null), 3000);
      if (changePassword) setChangePassword(false);
      setPassword("");
    } catch (err: any) {
      setSaveMsg({ type: "error", text: err.message || "Erreur de mise a jour." });
    } finally {
      setSaving(false);
    }
  }

  // Password criteria mock
  const hasNumber = /\d/.test(password);
  const hasUpper = /[A-Z]/.test(password);
  const hasLower = /[a-z]/.test(password);
  const hasSymbol = /[!@#$%^&*(),.?":{}|<>]/.test(password);
  const hasLength = password.length >= 12;

  const Pill = ({ active, label }: { active: boolean; label: string }) => (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium transition-colors ${active ? 'bg-primary-100 text-primary-700' : 'bg-gray-100 text-gray-400'}`}>
      {active ? (
        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg>
      ) : (
        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}><path strokeLinecap="round" strokeLinejoin="round" d="M20 12H4" /></svg>
      )}
      {label}
    </span>
  );

  if (loading) {
    return (
      <div className="flex h-[60vh] items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary-500 border-t-transparent" />
          <p className="text-[13px] text-gray-400">Chargement du profil...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="page-enter max-w-5xl">
      <h1 className="text-2xl font-bold tracking-tight text-gray-800">
        Bienvenue, {profile?.first_name || user?.first_name || "Docteur"}
      </h1>

      {saveMsg && (
        <div className={`mt-4 rounded-lg px-4 py-3 text-[13px] font-medium ${saveMsg.type === 'success' ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-red-50 text-red-700 border border-red-200'}`}>
          {saveMsg.text}
        </div>
      )}

      {/* Main Form Card */}
      <div className="mt-6 rounded-2xl border border-gray-100 bg-white shadow-card">
        <div className="p-8">
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            <div>
              <label className="mb-2 block text-[13px] font-medium text-gray-700">Prenom</label>
              <input
                type="text"
                value={editFirst}
                onChange={(e) => setEditFirst(e.target.value)}
                className="w-full rounded-xl border border-gray-200 px-4 py-3 text-[14px] text-gray-800 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/20"
              />
            </div>
            <div>
              <label className="mb-2 block text-[13px] font-medium text-gray-700">Nom</label>
              <input
                type="text"
                value={editLast}
                onChange={(e) => setEditLast(e.target.value)}
                className="w-full rounded-xl border border-gray-200 px-4 py-3 text-[14px] text-gray-800 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/20"
              />
            </div>
            
            <div>
              <label className="mb-2 block text-[13px] font-medium text-gray-700">Email</label>
              <input
                type="email"
                value={editEmail}
                readOnly
                className="w-full rounded-xl border border-gray-200 bg-gray-50 px-4 py-3 text-[14px] text-gray-500 cursor-not-allowed"
              />
            </div>
            
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="block text-[13px] font-medium text-gray-700">Mot de passe</label>
                <button 
                  onClick={() => setChangePassword(!changePassword)} 
                  className="text-[12px] font-semibold text-primary-500 hover:text-primary-600"
                >
                  {changePassword ? "Annuler" : "Modifier"}
                </button>
              </div>
              
              {changePassword ? (
                <div>
                  <div className="relative">
                    <span className="absolute inset-y-0 left-0 flex items-center pl-4 text-primary-400">
                      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
                      </svg>
                    </span>
                    <input
                      type={showPassword ? "text" : "password"}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Saisir le mot de passe"
                      className="w-full rounded-xl border border-gray-200 pl-11 pr-11 py-3 text-[14px] text-gray-800 placeholder-primary-300 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/20"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute inset-y-0 right-0 flex items-center pr-4 text-gray-400 hover:text-gray-600"
                    >
                      {showPassword ? (
                        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.242 4.242L9.88 9.88" /></svg>
                      ) : (
                        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" /><path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
                      )}
                    </button>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Pill active={hasNumber} label="1 chiffre" />
                    <Pill active={hasUpper} label="1 majuscule" />
                    <Pill active={hasLower} label="1 minuscule" />
                    <Pill active={hasSymbol} label="1 symbole" />
                    <Pill active={hasLength} label="12 caracteres" />
                  </div>
                </div>
              ) : (
                <div className="w-full rounded-xl border border-gray-100 bg-gray-50 px-4 py-3 text-[14px] text-gray-400">
                  ••••••••••
                </div>
              )}
            </div>
          </div>
          
          <div className="mt-8 flex justify-end">
            <button
              onClick={handleSave}
              disabled={saving}
              className="rounded-xl bg-gradient-to-r from-primary-500 to-primary-600 px-8 py-3 text-[14px] font-bold text-white shadow-lg shadow-primary-500/25 transition hover:shadow-xl hover:shadow-primary-500/30 disabled:opacity-50"
            >
              {saving ? "Sauvegarde..." : "Mettre a jour"}
            </button>
          </div>
        </div>
      </div>

      {/* Role & Permissions Card */}
      <div className="mt-8">
        <h2 className="mb-4 flex items-center gap-2 text-[16px] font-bold text-gray-800">
          <svg className="h-5 w-5 text-primary-500" fill="currentColor" viewBox="0 0 24 24"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
          Role et permissions
        </h2>
        <div className="rounded-2xl border border-gray-100 bg-white p-6 shadow-card">
          <div className="flex flex-col lg:flex-row lg:items-center gap-6">
            <div className="inline-flex flex-col items-center justify-center rounded-2xl border border-primary-200 bg-primary-50/50 px-8 py-5 min-w-[180px]">
              <span className="text-primary-500">
                <svg className="h-8 w-8" fill="currentColor" viewBox="0 0 24 24"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
              </span>
              <span className="mt-2 text-[15px] font-bold text-primary-700 capitalize">
                {profile?.speciality || user?.role || "Psychiatre"}
              </span>
              <span className="mt-0.5 text-[11px] font-bold text-primary-400">(A)</span>
            </div>
            <div className="flex-1">
              <h3 className="text-[14px] font-bold text-gray-800 mb-1">Droits d'accès</h3>
              <p className="text-[13px] leading-relaxed text-gray-500">
                En tant que psychiatre, vous disposez d'un accès complet à vos patients assignés. Vous pouvez consulter l'évolution détaillée de leurs biomarqueurs, analyser les alertes générées par l'IA (Machine Learning) pour détecter d'éventuelles rechutes, et organiser des séances de téléconsultation d'urgence en cas de score de risque élevé.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
