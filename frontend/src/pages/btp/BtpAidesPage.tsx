import { useState, useMemo, useEffect } from 'react';
import { IconSubvention, IconRecherche, IconInfo, IconTendance, IconCalendrier, IconSucces } from '@/components/icons';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { PageHeader } from '@/components/shared/PageHeader';
import { useAideStore } from '@/stores/useAideStore';
import { useAuthStore } from '@/stores/useAuthStore';
import { aideService } from '@/services/aide.service';
import { cn } from '@/lib/utils';
import type { Aide, AideCategory } from '@/types';

const CATEGORY_COLORS: Record<string, string> = {
  etat_drac: 'bg-info-muted text-info',
  region: 'bg-cat-violet-soft text-cat-violet',
  departement: 'bg-cat-10-soft text-cat-10',
  europe: 'bg-cat-1-soft text-cat-1',
  fondation_patrimoine: 'bg-warning-muted text-warning',
  mecenat: 'bg-cat-2-soft text-cat-2',
  fiscalite: 'bg-success-muted text-success',
  autre: 'bg-muted text-muted-foreground',
};

const CATEGORY_LABELS: Record<string, string> = {
  etat_drac: 'État / DRAC',
  region: 'Région',
  departement: 'Département',
  europe: 'Europe',
  fondation_patrimoine: 'Fondation Patrimoine',
  mecenat: 'Mécénat',
  fiscalite: 'Fiscalité',
  autre: 'Autre',
};

export function BtpAidesPage() {
  const aides = useAideStore((s) => s.aides);
  const setAides = useAideStore((s) => s.setAides);
  const token = useAuthStore((s) => s.token);
  const [search, setSearch] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<AideCategory | 'all'>('all');
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // Le catalogue complet vit ici, la seule page qui le lit : la carte dépliée
  // affiche descriptionLongue, la démarche et les pièces requises. Il était
  // chargé pour tout le monde depuis AppLayout, y compris sur le dashboard qui
  // n'en lit rien — et jamais dans l'espace BTP, où cette page est servie.
  useEffect(() => {
    if (!token || aides.length > 0) return;
    aideService.getAll().then(setAides).catch(console.error);
  }, [token, aides.length, setAides]);

  const filtered = useMemo(() => {
    let result = aides;
    if (selectedCategory !== 'all') {
      result = result.filter((a) => a.categorie === selectedCategory);
    }
    if (search) {
      const q = search.toLowerCase();
      result = result.filter(
        (a) =>
          a.nom.toLowerCase().includes(q) ||
          a.nomCourt.toLowerCase().includes(q) ||
          a.organisme.toLowerCase().includes(q) ||
          a.description.toLowerCase().includes(q)
      );
    }
    return result;
  }, [aides, selectedCategory, search]);

  const categories = useMemo(
    () => [...new Set(aides.map((a) => a.categorie))],
    [aides]
  );

  const totalTaux = useMemo(() => {
    const withTaux = aides.filter((a) => a.tauxMax);
    return withTaux.reduce((s, a) => s + (a.tauxMax ?? 0), 0) / (withTaux.length || 1);
  }, [aides]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Catalogue des aides patrimoine"
        description="Toutes les aides disponibles pour vos arguments commerciaux"
      />

      {/* Info banner BTP */}
      <Card className="border-warning/30 bg-warning-muted">
        <CardContent className="pt-4 pb-3">
          <div className="flex items-start gap-3">
            <IconTendance className="h-5 w-5 text-warning shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-foreground">
                Utilisez ce catalogue comme outil commercial
              </p>
              <p className="text-xs text-muted-foreground mt-0.5">
                Identifiez les aides applicables à un monument prospect pour démontrer que son projet peut être
                financé à {Math.round(totalTaux)}% en moyenne. C'est votre meilleur argument pour déclencher les travaux.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Stats rapides */}
      <div className="grid grid-cols-3 gap-3">
        <Card className="bg-muted/40">
          <CardContent className="pt-4 pb-3">
            <p className="text-xs text-muted-foreground">{aides.length} aides disponibles</p>
            <p className="text-xl font-bold">{aides.filter(a => a.tauxMax).length}</p>
            <p className="text-xs text-muted-foreground">avec taux défini</p>
          </CardContent>
        </Card>
        <Card className="bg-info-muted">
          <CardContent className="pt-4 pb-3">
            <p className="text-xs text-muted-foreground">Taux max le plus élevé</p>
            <p className="text-xl font-bold text-info">
              {Math.max(...aides.filter(a => a.tauxMax).map(a => a.tauxMax ?? 0))}%
            </p>
            <p className="text-xs text-muted-foreground">FIP petites communes</p>
          </CardContent>
        </Card>
        <Card className="bg-success-muted">
          <CardContent className="pt-4 pb-3">
            <p className="text-xs text-muted-foreground">Aides avec date limite</p>
            <p className="text-xl font-bold text-success">
              {aides.filter(a => a.dateLimite).length}
            </p>
            <p className="text-xs text-muted-foreground">à déclencher rapidement</p>
          </CardContent>
        </Card>
      </div>

      {/* Filtres */}
      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-48">
          <IconRecherche className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Rechercher une aide..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant={selectedCategory === 'all' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setSelectedCategory('all')}
          >
            Toutes
          </Button>
          {categories.map((cat) => (
            <Button
              key={cat}
              variant={selectedCategory === cat ? 'default' : 'outline'}
              size="sm"
              onClick={() => setSelectedCategory(cat)}
            >
              {CATEGORY_LABELS[cat]}
            </Button>
          ))}
        </div>
      </div>

      {/* Liste */}
      <div className="space-y-3">
        {filtered.map((aide) => (
          <AideRow
            key={aide.id}
            aide={aide}
            expanded={expandedId === aide.id}
            onToggle={() => setExpandedId(expandedId === aide.id ? null : aide.id)}
          />
        ))}
        {filtered.length === 0 && (
          <div className="text-center py-8">
            <IconSubvention className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
            <p className="text-muted-foreground text-sm">Aucune aide correspondante</p>
          </div>
        )}
      </div>
    </div>
  );
}

function AideRow({
  aide,
  expanded,
  onToggle,
}: {
  aide: Aide;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <Card className="transition-all">
      <CardContent className="pt-4 pb-3">
        <div className="space-y-3">
          {/* Header */}
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <div className="flex items-start gap-2 flex-wrap">
                <Badge className={cn('text-xs shrink-0', CATEGORY_COLORS[aide.categorie])}>
                  {CATEGORY_LABELS[aide.categorie]}
                </Badge>
                {aide.dateLimite && (
                  <Badge variant="outline" className="text-xs text-warning border-warning/40">
                    <IconCalendrier className="h-3 w-3 mr-1" />
                    Limite : {new Date(aide.dateLimite).toLocaleDateString('fr-FR')}
                  </Badge>
                )}
              </div>
              <h3 className="font-semibold text-sm mt-1.5">{aide.nom}</h3>
              <p className="text-xs text-muted-foreground mt-0.5">{aide.organisme}</p>
            </div>
            <div className="text-right shrink-0">
              {aide.tauxMax && (
                <p className="text-xl font-bold text-primary">{aide.tauxMax}%</p>
              )}
              {aide.montantMax && (
                <p className="text-xs text-muted-foreground">
                  max {aide.montantMax.toLocaleString('fr-FR')} €
                </p>
              )}
            </div>
          </div>

          <p className="text-sm text-muted-foreground">{aide.description}</p>

          {/* Critères résumés */}
          <div className="flex flex-wrap gap-1.5">
            {aide.criteres.protectionRequise?.map((p) => (
              <Badge key={p} variant="secondary" className="text-xs">
                {p === 'classe' ? 'Classé MH' : p === 'inscrit' ? 'Inscrit MH' : p}
              </Badge>
            ))}
            {aide.criteres.communeDeMoins10000Hab && (
              <Badge variant="secondary" className="text-xs">Communes &lt; 10 000 hab.</Badge>
            )}
            {aide.criteres.regionEligible?.map((r) => (
              <Badge key={r} variant="outline" className="text-xs capitalize">
                {r.replace(/-/g, ' ')}
              </Badge>
            ))}
          </div>

          {/* Expand */}
          <div className="flex items-center justify-between pt-1 border-t">
            <Button
              variant="ghost"
              size="sm"
              className="text-xs h-7"
              onClick={onToggle}
            >
              <IconInfo className="h-3.5 w-3.5 mr-1" />
              {expanded ? 'Moins d\'infos' : 'Détail & démarche'}
            </Button>
            <div className="flex items-center gap-1.5">
              {aide.criteres.architecteRequis && (
                <span className="text-xs text-muted-foreground">Architecte requis</span>
              )}
              <span className="text-xs text-muted-foreground">
                {aide.delaiInstruction}
              </span>
            </div>
          </div>

          {/* Expanded content */}
          {expanded && (
            <div className="pt-3 border-t space-y-4">
              {aide.descriptionLongue && (
                <div>
                  <p className="text-xs font-medium text-muted-foreground mb-1">Description complète</p>
                  <p className="text-sm">{aide.descriptionLongue}</p>
                </div>
              )}

              <div>
                <p className="text-xs font-medium text-muted-foreground mb-2">Démarche</p>
                <p className="text-sm whitespace-pre-line">{aide.demarcheDescription}</p>
              </div>

              <div>
                <p className="text-xs font-medium text-muted-foreground mb-2">
                  Documents requis ({aide.documentsRequis.length})
                </p>
                <div className="space-y-1">
                  {aide.documentsRequis.map((raw, i) => {
                    const nom = typeof raw === 'string' ? raw : raw.nom;
                    return (
                      <div key={i} className="flex items-start gap-2 text-xs">
                        <IconSucces className="h-3.5 w-3.5 text-muted-foreground shrink-0 mt-0.5" />
                        <span>{nom}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
