import { useParams, Link, useNavigate } from 'react-router';
import {
  ArrowLeft, MapPin, Shield, Phone,
  User, Mail, FileText, TrendingUp, CheckCircle2,
  AlertCircle, Clock, Trash2, ExternalLink,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useProspectStore } from '@/stores/useProspectStore';
import { formatCurrency } from '@/lib/format-utils';
import { cn } from '@/lib/utils';
import type { ProspectStatus } from '@/types';

const STATUS_CONFIG: Record<ProspectStatus, { label: string; color: string }> = {
  a_contacter: { label: 'À contacter', color: 'bg-gray-100 text-gray-700' },
  contacte: { label: 'Contacté', color: 'bg-blue-100 text-blue-700' },
  en_discussion: { label: 'En discussion', color: 'bg-amber-100 text-amber-700' },
  devis_envoye: { label: 'Devis envoyé', color: 'bg-purple-100 text-purple-700' },
  gagne: { label: 'Gagné ✓', color: 'bg-emerald-100 text-emerald-700' },
  perdu: { label: 'Perdu', color: 'bg-red-100 text-red-700' },
};

const PROTECTION_LABELS: Record<string, string> = {
  classe: 'Classé Monument Historique',
  inscrit: 'Inscrit Monument Historique',
  abords: 'Périmètre de protection',
  spr: 'Site Patrimonial Remarquable',
  non_protege: 'Non protégé',
};

export function BtpProspectDetailPage() {
  const { prospectId } = useParams<{ prospectId: string }>();
  const getProspect = useProspectStore((s) => s.getProspect);
  const updateStatut = useProspectStore((s) => s.updateStatut);
  const deleteProspect = useProspectStore((s) => s.deleteProspect);
  const navigate = useNavigate();

  const prospect = prospectId ? getProspect(prospectId) : undefined;

  if (!prospect) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">Prospect introuvable</p>
        <Button asChild variant="outline" className="mt-3">
          <Link to="/btp/prospects">Retour aux prospects</Link>
        </Button>
      </div>
    );
  }

  const conf = STATUS_CONFIG[prospect.statut];

  const tauxRestantCharge = 100 - prospect.tauxCouvertureEstime;
  const montantRestant = prospect.montantTravaux
    ? prospect.montantTravaux * (tauxRestantCharge / 100)
    : undefined;

  return (
    <div className="space-y-6">
      {/* Back + Actions */}
      <div className="flex items-center justify-between">
        <Button asChild variant="ghost" size="sm">
          <Link to="/btp/prospects">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Retour aux prospects
          </Link>
        </Button>
        <div className="flex items-center gap-2">
          <Select
            value={prospect.statut}
            onValueChange={(v) => updateStatut(prospect.id, v as ProspectStatus)}
          >
            <SelectTrigger className="w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {(Object.entries(STATUS_CONFIG) as [ProspectStatus, typeof STATUS_CONFIG[ProspectStatus]][]).map(
                ([key, c]) => (
                  <SelectItem key={key} value={key}>
                    {c.label}
                  </SelectItem>
                )
              )}
            </SelectContent>
          </Select>
          <Button
            variant="ghost"
            size="icon"
            className="text-destructive hover:text-destructive"
            onClick={() => {
              deleteProspect(prospect.id);
              navigate('/btp/prospects');
            }}
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Header */}
      <div className="space-y-1">
        <div className="flex items-start gap-3">
          <div className="flex-1 min-w-0">
            <h1 className="text-2xl font-bold tracking-tight truncate">{prospect.monumentNom}</h1>
            <div className="flex items-center gap-2 mt-1 text-sm text-muted-foreground">
              <MapPin className="h-4 w-4 shrink-0" />
              <span>{prospect.adresse}, {prospect.codePostal} {prospect.commune}</span>
            </div>
          </div>
          <Badge className={cn('text-sm shrink-0', conf.color)}>{conf.label}</Badge>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Monument + contact */}
        <div className="lg:col-span-2 space-y-6">
          {/* Monument info */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <Shield className="h-4 w-4 text-primary" />
                Caractéristiques du monument
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid grid-cols-2 gap-4">
                <InfoRow label="Protection" value={PROTECTION_LABELS[prospect.protection] ?? prospect.protection} />
                <InfoRow label="Propriétaire" value={formatOwner(prospect.proprietaire)} />
                <InfoRow label="Région" value={prospect.region} />
                <InfoRow label="Département" value={prospect.departement} />
                {prospect.superficie && (
                  <InfoRow label="Superficie" value={`${prospect.superficie} m²`} />
                )}
                {prospect.etatConservation && (
                  <InfoRow label="État de conservation" value={prospect.etatConservation} />
                )}
              </div>

              {prospect.descriptionEtat && (
                <div className="pt-2 border-t">
                  <p className="text-xs text-muted-foreground mb-1">État constaté</p>
                  <p className="text-sm">{prospect.descriptionEtat}</p>
                </div>
              )}

              <div className="pt-2 border-t">
                <p className="text-xs text-muted-foreground mb-2">Travaux envisagés</p>
                <div className="flex flex-wrap gap-1.5">
                  {prospect.travauxEnvisages.map((t) => (
                    <Badge key={t} variant="secondary" className="text-xs capitalize">
                      {t.replace(/_/g, ' ')}
                    </Badge>
                  ))}
                </div>
              </div>

              {prospect.referenceMerimee && (
                <div className="flex items-center gap-2 pt-2 border-t">
                  <ExternalLink className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="text-xs text-muted-foreground">
                    Référence Mérimée : <span className="font-mono">{prospect.referenceMerimee}</span>
                  </span>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Contact */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <User className="h-4 w-4 text-primary" />
                Contact
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {prospect.contactNom && (
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                    <User className="h-4 w-4 text-primary" />
                  </div>
                  <div>
                    <p className="text-sm font-medium">{prospect.contactNom}</p>
                    {prospect.contactFonction && (
                      <p className="text-xs text-muted-foreground">{prospect.contactFonction}</p>
                    )}
                  </div>
                </div>
              )}

              <div className="grid grid-cols-1 gap-2">
                {prospect.contactEmail && (
                  <a
                    href={`mailto:${prospect.contactEmail}`}
                    className="flex items-center gap-2 text-sm text-primary hover:underline"
                  >
                    <Mail className="h-4 w-4 shrink-0" />
                    {prospect.contactEmail}
                  </a>
                )}
                {prospect.contactTelephone && (
                  <a
                    href={`tel:${prospect.contactTelephone}`}
                    className="flex items-center gap-2 text-sm text-primary hover:underline"
                  >
                    <Phone className="h-4 w-4 shrink-0" />
                    {prospect.contactTelephone}
                  </a>
                )}
              </div>

              {prospect.dateProchainContact && (
                <div className="flex items-center gap-2 pt-2 border-t">
                  <Clock className="h-4 w-4 text-amber-500 shrink-0" />
                  <div>
                    <p className="text-xs text-muted-foreground">Prochain contact</p>
                    <p className="text-sm font-medium">
                      {new Date(prospect.dateProchainContact).toLocaleDateString('fr-FR', {
                        weekday: 'long',
                        day: 'numeric',
                        month: 'long',
                        year: 'numeric',
                      })}
                    </p>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Notes */}
          {prospect.notes && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <FileText className="h-4 w-4 text-primary" />
                  Notes commerciales
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm whitespace-pre-line">{prospect.notes}</p>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Right: Financement */}
        <div className="space-y-6">
          {/* Financement synthèse */}
          <Card className={cn(
            'border-2',
            prospect.financementIdentifie ? 'border-emerald-200 bg-emerald-50/50' : 'border-muted'
          )}>
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <TrendingUp className={cn('h-4 w-4', prospect.financementIdentifie ? 'text-emerald-600' : 'text-muted-foreground')} />
                Analyse financement
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {prospect.financementIdentifie ? (
                <>
                  <div className="text-center py-2">
                    <p className="text-xs text-muted-foreground mb-1">Financement public identifié</p>
                    <p className="text-3xl font-bold text-emerald-700">
                      {formatCurrency(prospect.totalFinancementPotentiel)}
                    </p>
                    <p className="text-sm text-emerald-600 mt-1">
                      soit {prospect.tauxCouvertureEstime}% des travaux
                    </p>
                  </div>

                  {prospect.montantTravaux && (
                    <div className="space-y-2 border-t pt-3">
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">Travaux estimés</span>
                        <span className="font-medium">{formatCurrency(prospect.montantTravaux)}</span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">Aides & subventions</span>
                        <span className="font-medium text-emerald-700">
                          — {formatCurrency(prospect.totalFinancementPotentiel)}
                        </span>
                      </div>
                      <div className="flex justify-between text-sm font-bold border-t pt-2">
                        <span>Reste à charge propriétaire</span>
                        <span>{formatCurrency(montantRestant ?? 0)}</span>
                      </div>
                    </div>
                  )}

                  <div className="bg-emerald-100/80 rounded-lg p-3">
                    <p className="text-xs text-emerald-800 font-medium mb-1">
                      ✓ Argument commercial clé
                    </p>
                    <p className="text-xs text-emerald-700">
                      Avec {prospect.tauxCouvertureEstime}% du projet financé par des aides
                      publiques, le reste à charge est considérablement réduit.
                      C'est le moment d'entreprendre les travaux.
                    </p>
                  </div>
                </>
              ) : (
                <div className="text-center py-4">
                  <AlertCircle className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
                  <p className="text-sm text-muted-foreground">
                    Financement à analyser
                  </p>
                  <Button asChild variant="outline" size="sm" className="mt-3">
                    <Link to="/btp/aides">
                      Lancer un diagnostic
                    </Link>
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Checklist commerciale */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Checklist commerciale</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {[
                { label: 'Monument identifié', done: true },
                { label: 'Contact établi', done: prospect.statut !== 'a_contacter' },
                { label: 'Financement analysé', done: prospect.financementIdentifie },
                { label: 'En discussion', done: ['en_discussion', 'devis_envoye', 'gagne'].includes(prospect.statut) },
                { label: 'Devis envoyé', done: ['devis_envoye', 'gagne'].includes(prospect.statut) },
                { label: 'Marché signé', done: prospect.statut === 'gagne' },
              ].map((item) => (
                <div key={item.label} className="flex items-center gap-2">
                  {item.done ? (
                    <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
                  ) : (
                    <div className="h-4 w-4 rounded-full border-2 border-muted-foreground/30 shrink-0" />
                  )}
                  <span className={cn('text-sm', item.done ? 'text-foreground' : 'text-muted-foreground')}>
                    {item.label}
                  </span>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-sm font-medium capitalize">{value.replace(/_/g, ' ')}</p>
    </div>
  );
}

function formatOwner(type: string): string {
  const map: Record<string, string> = {
    public_commune: 'Commune',
    public_departement: 'Département',
    public_region: 'Région',
    public_etat: 'État',
    prive_personne_physique: 'Particulier',
    prive_sci: 'SCI',
    association: 'Association',
    mixte: 'Mixte',
  };
  return map[type] ?? type;
}
