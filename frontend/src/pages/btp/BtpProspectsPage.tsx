import { useState, useMemo } from 'react';
import { Link } from 'react-router';
import {
  Users, Search,
  ChevronRight, CheckCircle2, Clock, Phone, Target, AlertCircle,
  Building2, MapPin,
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { PageHeader } from '@/components/shared/PageHeader';
import { useAuthStore } from '@/stores/useAuthStore';
import { useProspectStore } from '@/stores/useProspectStore';
import { formatCurrency } from '@/lib/format-utils';
import { cn } from '@/lib/utils';
import type { Prospect, ProspectStatus } from '@/types';

const STATUS_CONFIG: Record<ProspectStatus, { label: string; color: string; icon: typeof Clock }> = {
  a_contacter: { label: 'À contacter', color: 'bg-gray-100 text-gray-700', icon: Clock },
  contacte: { label: 'Contacté', color: 'bg-blue-100 text-blue-700', icon: Phone },
  en_discussion: { label: 'En discussion', color: 'bg-amber-100 text-amber-700', icon: Users },
  devis_envoye: { label: 'Devis envoyé', color: 'bg-purple-100 text-purple-700', icon: Target },
  gagne: { label: 'Gagné ✓', color: 'bg-emerald-100 text-emerald-700', icon: CheckCircle2 },
  perdu: { label: 'Perdu', color: 'bg-red-100 text-red-700', icon: AlertCircle },
};

const PROTECTION_LABELS: Record<string, string> = {
  classe: 'Classé MH',
  inscrit: 'Inscrit MH',
  abords: 'Abords MH',
  spr: 'SPR',
  non_protege: 'Non protégé',
};

export function BtpProspectsPage() {
  const user = useAuthStore((s) => s.user);
  const prospects = useProspectStore((s) => s.prospects);
  const updateStatut = useProspectStore((s) => s.updateStatut);

  const [search, setSearch] = useState('');
  const [filterStatus, setFilterStatus] = useState<ProspectStatus | 'all'>('all');
  const [filterFinancement, setFilterFinancement] = useState<'all' | 'oui' | 'non'>('all');
  const userProspects = useMemo(
    () => prospects.filter((p) => p.btpUserId === user?.id),
    [prospects, user?.id]
  );

  const filtered = useMemo(() => {
    let result = userProspects;
    if (filterStatus !== 'all') {
      result = result.filter((p) => p.statut === filterStatus);
    }
    if (filterFinancement === 'oui') {
      result = result.filter((p) => p.financementIdentifie);
    } else if (filterFinancement === 'non') {
      result = result.filter((p) => !p.financementIdentifie);
    }
    if (search) {
      const q = search.toLowerCase();
      result = result.filter(
        (p) =>
          p.monumentNom.toLowerCase().includes(q) ||
          p.commune.toLowerCase().includes(q) ||
          (p.contactNom?.toLowerCase().includes(q) ?? false)
      );
    }
    return result;
  }, [userProspects, filterStatus, filterFinancement, search]);

  const totalCA = useMemo(
    () => filtered.reduce((s, p) => s + (p.montantTravaux ?? 0), 0),
    [filtered]
  );
  const totalFinancement = useMemo(
    () => filtered.filter((p) => p.financementIdentifie).reduce((s, p) => s + p.totalFinancementPotentiel, 0),
    [filtered]
  );

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <PageHeader
          title="Mes prospects"
          description="Monuments patrimoniaux identifiés avec leur potentiel de financement"
        />
        <Button asChild>
          <Link to="/btp/prospects/new">
            <Users className="h-4 w-4 mr-2" />
            Nouveau prospect
          </Link>
        </Button>
      </div>

      {/* Résumé */}
      <div className="grid grid-cols-3 gap-3">
        <Card className="bg-muted/40">
          <CardContent className="pt-4 pb-3">
            <p className="text-xs text-muted-foreground">Prospects filtrés</p>
            <p className="text-2xl font-bold">{filtered.length}</p>
          </CardContent>
        </Card>
        <Card className="bg-blue-50">
          <CardContent className="pt-4 pb-3">
            <p className="text-xs text-muted-foreground">CA potentiel</p>
            <p className="text-2xl font-bold text-blue-700">{formatCurrency(totalCA)}</p>
          </CardContent>
        </Card>
        <Card className="bg-emerald-50">
          <CardContent className="pt-4 pb-3">
            <p className="text-xs text-muted-foreground">Financements identifiés</p>
            <p className="text-2xl font-bold text-emerald-700">{formatCurrency(totalFinancement)}</p>
          </CardContent>
        </Card>
      </div>

      {/* Filtres */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-48">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Rechercher..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select value={filterStatus} onValueChange={(v) => setFilterStatus(v as ProspectStatus | 'all')}>
          <SelectTrigger className="w-44">
            <SelectValue placeholder="Statut" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Tous les statuts</SelectItem>
            {(Object.entries(STATUS_CONFIG) as [ProspectStatus, typeof STATUS_CONFIG[ProspectStatus]][]).map(
              ([key, conf]) => (
                <SelectItem key={key} value={key}>
                  {conf.label}
                </SelectItem>
              )
            )}
          </SelectContent>
        </Select>
        <Select value={filterFinancement} onValueChange={(v) => setFilterFinancement(v as 'all' | 'oui' | 'non')}>
          <SelectTrigger className="w-48">
            <SelectValue placeholder="Financement" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Tout le financement</SelectItem>
            <SelectItem value="oui">Financement identifié</SelectItem>
            <SelectItem value="non">Sans financement</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Liste des prospects */}
      {filtered.length === 0 ? (
        <div className="text-center py-12">
          <Users className="h-12 w-12 text-muted-foreground mx-auto mb-3" />
          <p className="text-muted-foreground">Aucun prospect trouvé</p>
          <Button asChild variant="outline" className="mt-3">
            <Link to="/btp/prospects/new">Ajouter un premier prospect</Link>
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {filtered.map((p) => (
            <ProspectCard
              key={p.id}
              prospect={p}
              onUpdateStatus={updateStatut}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function ProspectCard({
  prospect: p,
  onUpdateStatus,
}: {
  prospect: Prospect;
  onUpdateStatus: (id: string, status: ProspectStatus) => void;
}) {
  const conf = STATUS_CONFIG[p.statut];
  const StatusIcon = conf.icon;

  const daysUntil = p.dateProchainContact
    ? Math.ceil(
        (new Date(p.dateProchainContact).getTime() - Date.now()) / (1000 * 60 * 60 * 24)
      )
    : null;

  return (
    <Card className={cn(
      'transition-all hover:shadow-md',
      p.statut === 'gagne' && 'border-emerald-200 bg-emerald-50/30',
      p.statut === 'perdu' && 'opacity-60',
    )}>
      <CardContent className="pt-4 pb-3">
        <div className="space-y-3">
          {/* Header */}
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0 flex-1">
              <p className="font-semibold text-sm leading-tight truncate">{p.monumentNom}</p>
              <div className="flex items-center gap-1.5 mt-0.5 text-xs text-muted-foreground">
                <MapPin className="h-3 w-3 shrink-0" />
                <span className="truncate">{p.commune} ({p.departement})</span>
              </div>
            </div>
            <Badge className={cn('text-xs shrink-0', conf.color)}>
              <StatusIcon className="h-3 w-3 mr-1" />
              {conf.label}
            </Badge>
          </div>

          {/* Protection + travaux */}
          <div className="flex items-center gap-2 flex-wrap">
            <Badge variant="outline" className="text-xs">
              {PROTECTION_LABELS[p.protection] ?? p.protection}
            </Badge>
            {p.travauxEnvisages.slice(0, 2).map((t) => (
              <Badge key={t} variant="secondary" className="text-xs capitalize">
                {t.replace(/_/g, ' ')}
              </Badge>
            ))}
            {p.travauxEnvisages.length > 2 && (
              <span className="text-xs text-muted-foreground">
                +{p.travauxEnvisages.length - 2}
              </span>
            )}
          </div>

          {/* Financement */}
          {p.financementIdentifie ? (
            <div className="flex items-center justify-between bg-emerald-50 rounded-lg px-3 py-2">
              <div>
                <p className="text-xs text-muted-foreground">Financement identifié</p>
                <p className="text-sm font-bold text-emerald-700">
                  {formatCurrency(p.totalFinancementPotentiel)}
                </p>
              </div>
              <div className="text-right">
                <p className="text-xs text-muted-foreground">Couverture estimée</p>
                <p className="text-sm font-bold text-emerald-700">{p.tauxCouvertureEstime}%</p>
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-2 bg-muted/50 rounded-lg px-3 py-2">
              <AlertCircle className="h-4 w-4 text-muted-foreground shrink-0" />
              <p className="text-xs text-muted-foreground">Financement à identifier</p>
            </div>
          )}

          {/* Montant travaux + contact */}
          <div className="flex items-center justify-between">
            <div>
              {p.montantTravaux && (
                <span className="text-xs text-muted-foreground">
                  Marché estimé : <span className="font-medium text-foreground">{formatCurrency(p.montantTravaux)}</span>
                </span>
              )}
            </div>
            {daysUntil !== null && (
              <Badge
                className={cn(
                  'text-xs',
                  daysUntil <= 0 ? 'bg-red-100 text-red-700' :
                  daysUntil <= 3 ? 'bg-amber-100 text-amber-700' :
                  'bg-gray-100 text-gray-700'
                )}
              >
                <Phone className="h-3 w-3 mr-1" />
                {daysUntil <= 0 ? 'Relance aujourd\'hui' : `Relance J-${daysUntil}`}
              </Badge>
            )}
          </div>

          {/* Contact */}
          {p.contactNom && (
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground border-t pt-2">
              <Building2 className="h-3 w-3 shrink-0" />
              <span className="truncate">{p.contactNom}</span>
              {p.contactFonction && (
                <span className="text-muted-foreground/60">— {p.contactFonction}</span>
              )}
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center justify-between pt-1">
            <div className="flex gap-1">
              {p.statut !== 'gagne' && p.statut !== 'perdu' && (
                <Select
                  value={p.statut}
                  onValueChange={(v) => onUpdateStatus(p.id, v as ProspectStatus)}
                >
                  <SelectTrigger className="h-7 text-xs w-36">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {(Object.entries(STATUS_CONFIG) as [ProspectStatus, typeof STATUS_CONFIG[ProspectStatus]][]).map(
                      ([key, conf]) => (
                        <SelectItem key={key} value={key} className="text-xs">
                          {conf.label}
                        </SelectItem>
                      )
                    )}
                  </SelectContent>
                </Select>
              )}
            </div>
            <Button asChild variant="ghost" size="sm" className="h-7 text-xs">
              <Link to={`/btp/prospects/${p.id}`}>
                Détails
                <ChevronRight className="h-3.5 w-3.5 ml-1" />
              </Link>
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
