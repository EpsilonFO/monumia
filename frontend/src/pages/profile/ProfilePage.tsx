import { useState } from 'react';
import { useNavigate } from 'react-router';
import { toast } from 'sonner';
import {
  IconEnregistrer,
  IconCompte,
  IconContact,
  IconTelephone,
  IconProtection,
  IconSucces,
  IconDeconnexion,
} from '@/components/icons';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { C, SERIF } from '@/lib/brand';
import { computeProfileCompletion } from '@/lib/profile-completion';
import { authService } from '@/services/auth.service';
import { useAuthStore } from '@/stores/useAuthStore';
import { isValidPhone } from '@/lib/phone';

export function ProfilePage() {
  const user = useAuthStore((s) => s.user);
  const updateProfile = useAuthStore((s) => s.updateProfile);
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();

  const [form, setForm] = useState({
    prenom: user?.prenom ?? '',
    nom: user?.nom ?? '',
    telephone: user?.telephone ?? '',
  });
  const [saving, setSaving] = useState(false);
  const [phoneError, setPhoneError] = useState<string | null>(null);
  const [resetState, setResetState] = useState<'idle' | 'sending' | 'sent'>('idle');

  if (!user) return null;
  const currentUser = user;
  const completion = computeProfileCompletion(currentUser);

  const handlePhoneChange = (value: string) => {
    setForm({ ...form, telephone: value });
    setPhoneError(value && !isValidPhone(value) ? 'Numéro invalide (ex : 06 12 34 56 78)' : null);
  };

  const handleSave = async () => {
    if (!isValidPhone(form.telephone)) {
      setPhoneError('Numéro invalide (ex : 06 12 34 56 78)');
      return;
    }
    setSaving(true);
    try {
      await updateProfile({
        prenom: form.prenom,
        nom: form.nom,
        telephone: form.telephone || undefined,
      });
      toast.success('Profil mis à jour');
    } catch (e: any) {
      toast.error(e.message || 'Erreur lors de la mise à jour');
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    setResetState('sending');
    try {
      await authService.requestPasswordReset(currentUser.email);
      setResetState('sent');
      toast.success('Email envoyé');
    } catch (e: any) {
      setResetState('idle');
      toast.error(e.message || "Impossible d'envoyer l'email pour le moment");
    }
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Bonjour' : hour < 18 ? 'Bon après-midi' : 'Bonsoir';
  const initials = `${currentUser.prenom?.[0] ?? ''}${currentUser.nom?.[0] ?? ''}`.toUpperCase();
  const complete = completion.percent >= 100;

  const inputCls =
    'h-11 text-[15px] bg-card border-border focus:border-primary focus:ring-primary/10 font-sans';

  return (
    <div className="flex flex-col gap-5">
      {/* ═════════ CARTE IDENTITÉ — tout au même endroit, modifiable ═════════ */}
      <section className="overflow-hidden rounded-2xl border border-border">
        {/* Bandeau : jauge + accueil */}
        <div
          className="flex flex-col gap-5 p-6 sm:flex-row sm:items-center sm:gap-7 sm:px-8"
          style={{ background: 'linear-gradient(120deg, var(--secondary) 0%, var(--card) 62%)' }}
        >
          <span
            className="flex h-[88px] w-[88px] shrink-0 items-center justify-center rounded-full text-[26px] font-semibold"
            style={{ background: C.paleBlue, color: C.blue, fontFamily: SERIF }}
          >
            {initials || <IconCompte className="h-9 w-9" />}
          </span>

          <div className="min-w-0 flex-1">
            <span
              className="inline-flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.2em]"
              style={{ color: C.blue }}
            >
              <span aria-hidden style={{ width: 22, height: 2, borderRadius: 2, background: C.orange }} />
              Mon espace
            </span>
            <h1
              className="mt-1.5 text-[clamp(1.7rem,3.5vw,2.4rem)] leading-[1.05]"
              style={{ fontFamily: 'var(--font-serif)', color: C.ink }}
            >
              {greeting}, <span style={{ color: C.blue }}>{currentUser.prenom}</span>
            </h1>

            <div className="mt-3 flex flex-wrap items-center gap-2.5">
              <span className="inline-flex items-center gap-1.5 text-[12.5px]" style={{ color: C.grayMuted }}>
                <IconSucces className="h-3.5 w-3.5" style={{ color: complete ? C.orange : C.grayMuted }} />
                {complete ? 'Profil complet' : 'Profil presque complet'}
              </span>
            </div>
          </div>
        </div>

        {/* Corps : formulaire modifiable */}
        <div className="space-y-5 border-t border-border bg-card px-6 py-6 sm:px-8">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field id="prenom" label="Prénom" icon={<IconCompte className="h-4 w-4" />}>
              <Input id="prenom" value={form.prenom} onChange={(e) => setForm({ ...form, prenom: e.target.value })} className={inputCls} />
            </Field>
            <Field id="nom" label="Nom" icon={<IconCompte className="h-4 w-4" />}>
              <Input id="nom" value={form.nom} onChange={(e) => setForm({ ...form, nom: e.target.value })} className={inputCls} />
            </Field>
            <Field id="telephone" label="Téléphone" icon={<IconTelephone className="h-4 w-4" />}>
              <Input
                id="telephone"
                value={form.telephone}
                onChange={(e) => handlePhoneChange(e.target.value)}
                placeholder="06 12 34 56 78"
                className={`${inputCls}${phoneError ? ' border-destructive focus:border-destructive focus:ring-destructive/10' : ''}`}
              />
              {phoneError && <p className="mt-1 text-[12px] text-destructive">{phoneError}</p>}
              {!form.telephone && !phoneError && (
                <p className="mt-1 text-[12px]" style={{ color: C.grayMuted }}>
                  Recommandé pour être joignable sur vos dossiers.
                </p>
              )}
            </Field>
            <Field id="email" label="Adresse email" icon={<IconContact className="h-4 w-4" />} hint="Non modifiable">
              <div className="flex h-11 items-center rounded-md border border-dashed border-border bg-[var(--secondary)]/40 px-3 text-[15px] text-muted-foreground">
                <span className="truncate">{currentUser.email}</span>
              </div>
            </Field>
          </div>

          <div className="flex flex-wrap items-center gap-3 pt-1">
            <button
              onClick={handleSave}
              disabled={saving || !!phoneError}
              className="inline-flex items-center gap-2 rounded-xl px-6 py-3 text-[14px] font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
              style={{ background: C.blue }}
            >
              <IconEnregistrer className="h-4 w-4" strokeWidth={1.8} />
              {saving ? 'Enregistrement…' : 'Enregistrer mes informations'}
            </button>
            <span className="text-[12.5px]" style={{ color: C.grayMuted }}>
              Vos informations restent privées et servent à préremplir vos dossiers.
            </span>
          </div>
        </div>
      </section>

      <Panel>
        <PanelHeader
          icon={<IconProtection className="h-4 w-4 text-primary" strokeWidth={1.8} />}
          title="Sécurité & connexion"
        />
        <div className="px-6 py-5">
          {resetState === 'sent' ? (
            <div className="flex items-start gap-3 rounded-xl p-4" style={{ background: C.paleBlue }}>
              <IconSucces className="mt-0.5 h-5 w-5 shrink-0" style={{ color: C.blue }} />
              <div className="text-[14px]" style={{ color: C.ink }}>
                <p className="font-medium">Un email vient d'être envoyé à {currentUser.email}.</p>
                <p className="mt-1" style={{ color: C.grayFg }}>
                  Ouvrez-le et cliquez sur le lien pour choisir un nouveau mot de passe. Pensez à vérifier vos courriers indésirables.
                </p>
                <button onClick={handleReset} className="mt-2 text-[13px] font-medium underline" style={{ color: C.blue }}>
                  Renvoyer l'email
                </button>
              </div>
            </div>
          ) : (
            <>
              <p className="text-[14px]" style={{ color: C.grayFg }}>
                Votre compte est protégé. Pour changer votre mot de passe, nous vous envoyons un lien
                sécurisé par email — rien à retenir.
              </p>
              <button
                onClick={handleReset}
                disabled={resetState === 'sending'}
                className="mt-3 inline-flex items-center gap-2 rounded-xl border px-5 py-3 text-[14px] font-semibold transition-colors hover:bg-[var(--secondary)] disabled:opacity-50"
                style={{ borderColor: C.border, color: C.blue }}
              >
                <IconContact className="h-4 w-4" />
                {resetState === 'sending' ? 'Envoi en cours…' : 'Recevoir un lien par email'}
              </button>
            </>
          )}
        </div>
      </Panel>

      {/* ═════════ DÉCONNEXION ═════════ */}
      <div className="pb-2">
        <button
          onClick={handleLogout}
          className="inline-flex items-center gap-2 rounded-xl border px-5 py-3 text-[14px] font-medium transition-colors hover:bg-[var(--destructive-muted)]"
          style={{ borderColor: C.border, color: C.danger }}
        >
          <IconDeconnexion className="h-4 w-4" />
          Se déconnecter
        </button>
      </div>
    </div>
  );
}

/* ── Sous-composants ── */

function Field({ id, label, icon, hint, children }: {
  id: string; label: string; icon: React.ReactNode; hint?: string; children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <Label htmlFor={id} className="flex items-center gap-1.5 text-[13px] font-medium text-foreground">
          <span style={{ color: C.blue }}>{icon}</span>
          {label}
        </Label>
        {hint && <span className="text-[11.5px]" style={{ color: C.grayMuted }}>{hint}</span>}
      </div>
      {children}
    </div>
  );
}

function Panel({ children }: { children: React.ReactNode }) {
  return <div className="overflow-hidden rounded-2xl border border-border bg-card">{children}</div>;
}

function PanelHeader({ icon, title, tint = 'blue' }: { icon: React.ReactNode; title: string; tint?: 'blue' | 'warning' }) {
  return (
    <div className="flex items-center gap-3 border-b border-border px-6 py-4">
      <span
        className={`flex h-8 w-8 items-center justify-center rounded-lg ${tint === 'warning' ? 'bg-warning-muted' : 'bg-secondary'}`}
      >
        {icon}
      </span>
      <h3 className="text-[17px]" style={{ fontFamily: SERIF, color: C.ink }}>{title}</h3>
    </div>
  );
}

