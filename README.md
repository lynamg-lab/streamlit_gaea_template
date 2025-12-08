# Modèle Streamlit GAEA — Scripts & Utilisation

> Ce dépôt contient des **modèles Streamlit** destinés à la formation des stagiaires (FR/EN).
> Les scripts du dossier `2_Scriptes/` peuvent évoluer ; ce README reste valide même quand de nouveaux
> fichiers sont ajoutés ou renommés.

---

## 📁 Dossiers

```
.
├─ 1_Donnees/                  # Données (sources & préparées)
│     └─ livestock_PREPARED_long.csv 
      └─ Emissions_livestock_Europe_RAW_FAO.csv
├─ 2_Scriptes/                 # Scripts Streamlit (exemples, versions FR/EN, variantes thématiques)
│  ├─ 01_preprocess_livestock_data_generic.py
│  ├─ 02_modele_streamlit_exemple_fr.py
│  └─ 02_streamlit_dashboard_template_eng.py
├─ requirements.txt
└─ README.md
```

### À propos de `2_Scriptes/`

Le dossier **2_Scriptes/** contient une ou plusieurs variantes d'application Streamlit :
- 01_preprocess_livestock_data_generic.py : préparer les données.
- 02_streamlit_dashboard_template_eng.py : version démonstration (ex. élevage « Totaux & Stocks »).
- 02_modele_streamlit_exemple_fr.py : version **française** (UI + commentaires).

Chaque script modele suit la même logique d'interface :
- Onglet **Tendances temporelles** (courbes) — export CSV.
- Onglet **Composition** (camembert Total_CO2e) — export CSV.
- Onglet **Carte** (Total_CO2e Europe, groupe `All`) — export CSV (Plotly requis).

---

## 📦 Installation

Prérequis : Python 3.9+

```bash
pip install -r requirements.txt
```
Contenu recommandé pour `requirements.txt` :

```
streamlit>=1.36
pandas>=2.0
altair>=5.0
plotly>=5.0  # requis pour l’onglet Carte
```

---

## 🧱 Schéma du CSV « préparé » (format long)

Colonnes **obligatoires** :

| Colonne          | Type   | Description                                                                  |
|------------------|--------|------------------------------------------------------------------------------|
| `Area`           | str    | Pays ou zone                                                                 |
| `Item`           | str    | Catégorie / item (ex. « Cattle », « Dairy Cattle »)                          |
| `Year`           | int    | Année                                                                        |
| `Metric`         | str    | `Total_CO2e` ou `Stocks` (périmètre du modèle)                               |
| `Value`          | float  | Valeur numérique                                                              |
| `item_kind`      | str    | `All` \| `aggregated` \| `atomic`                                          |
| `region_europe`  | bool   | True si le pays est en Europe                                                |
| `region_EU`      | bool   | True si le pays est dans l’UE                                                |
| `region_EUEEAUK` | bool   | True si UE/EEE/R.-Uni                                                        |

---

## ▶️ Lancer une application

Depuis la racine du dépôt (n'obliez pas de définer votre chemin à ce dossier):

```bash
# Exemple : lancer la variante « example »
# Il n'y a pas besoin de lancer la préparation des données pour lancer l'appli. 
# Le scripte 01_preprocess_livestock_data_generic.py est là pour vous donner exemple pour 
# vos propre données

streamlit run 2_Scriptes/02_modele_streamlit_exemple_fr.py

```

Sous Windows (PowerShell) :
```powershell
py -m streamlit run .\2_Scriptes\streamlit_dashboard_template_totals_stocks_example.py
```

Par défaut, le script lit un chemin `DEFAULT_PREPARED`. Si le fichier n’existe pas,
**uploadez** un CSV via l’interface.

---

## 🧭 Guide d’utilisation rapide

1. **Métrique & période** : choisissez `Total_CO2e` ou `Stocks`, puis la plage d’années.
2. **Groupe d’items** : `Tous` (exclusif), `Agrégés`, ou `Atomiques`.
3. **Mode d’affichage** : total **régional** (Europe/UE/UE+EEE+R.-Uni) ou **Pays**.
4. **Pays** : *Top 10* (option « Ajouter la Suisse ») ou *Personnalisé* (max 12).
5. **Onglets** : courbes / camembert / carte — **tous exportables en CSV**.

---

## 🛠️ Adapter à une autre thématique

- **Dupliquez** un script existant dans `2_Scriptes/` et renommez-le (ex. `transport_template_fr.py`).  
- Mettez à jour `DEFAULT_PREPARED` vers votre CSV au **même schéma**.  
- Ajustez `st.title(...)` et, si besoin, `metric_unit_label(...)` pour de nouvelles métriques.

---

## ✅ Checklist

- Le curseur d’années couvre la plage `Year` de votre CSV.  
- Le groupe d’items choisi contient des valeurs pour l’année ciblée.  
- Plotly installé pour l’onglet **Carte** ; noms pays compatibles (ex. UK → `United Kingdom`).

---

## ❓ Dépannage

- « CSV préparé introuvable » : corrigez `DEFAULT_PREPARED` ou uploadez un CSV.  
- Camembert vide : vérifier la présence de `item_kind == aggregated`.  
- Carte vide : valider `region_europe == True` et la présence de `Total_CO2e` pour `All`.  
- Purger cache : menu Streamlit → *Clear cache* (utilise `@st.cache_data`).

---

- Crédits : Équipe Statistiques (GAEA) — modèle commenté pour stagiaires (FR/EN).
