#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Modèle de tableau de bord Streamlit — Totaux & Stocks (Exemple)
==============================================================

Objectif
--------
Un modèle propre et bien commenté que d'autres équipes (transport, énergie, industrie, etc.)
peuvent copier pour créer des tableaux de bord **tant que le jeu de données préparé respecte le même schéma** :
colonnes comme Area, Item, Year, Metric, Value, item_kind, et drapeaux de région
(`region_europe`, `region_EU`, `region_EUEEAUK`).

Périmètre (volontairement restreint)
-----------------------------------
- **Métriques prises en charge** : "Total_CO2e" et "Stocks" uniquement.
- **Onglets** :
  1) Tendances temporelles — courbes par pays ou totaux régionaux (calculés à la volée via des booléens).
  2) Composition — un camembert des groupes agrégés pour **une année** (Total_CO2e uniquement).
  3) Carte — une choroplèthe de **Total_CO2e** pour les pays d'Europe (groupe All uniquement).

Comment adapter à d'autres domaines
-----------------------------------
- Remplacez le chemin CSV (DEFAULT_PREPARED) par le fichier préparé de votre secteur.
- Assurez-vous que votre prétraitement produit les mêmes noms de colonnes et les mêmes booléens régionaux.
- Conservez les catégories "item_kind" : "All" | "aggregated" | "atomic" pour réutiliser la logique d'interface.
- Adaptez les libellés, titres et couleurs à votre charte graphique.
- Ajoutez les métriques qui vous intéresse dans la fonction `metric_unit_label()`.

* "All" correspond au total de toutes les catégories d'items (ici, le total de tous les animaux).
** "aggregated" correspond aux grands groupes (ex. : Bovins, Volailles, etc.).
*** "atomic" correspond aux items les plus détaillés (ex. : Vaches laitières, Bovins viande, etc.).

Exécution (PowerShell)
----------------------
py -m streamlit run .\2_Scriptes\streamlit_dashboard_template_totals_stocks_example.py
"""

from __future__ import annotations
import streamlit as st, pandas as pd, altair as alt
from pathlib import Path

# --- Dépendance optionnelle pour la carte -------------------------------------------------------
# Nous préférons Plotly pour la choroplèthe. S'il n'est pas installé, on met un indicateur et on
# affiche ensuite un message d'erreur clair dans l'onglet Carte. Le reste de l'appli reste fonctionnel.
try:
    import plotly.express as px
    HAS_PLOTLY = True
    # Palette corporate (issue du thème GAEA) utilisée uniquement pour la choroplèthe Plotly
    CORP_SCALE = [
        [0.00, "#ABDDA4"],
        [0.11, "#66C2A5"],
        [0.22, "#3288BD"],
        [0.33, "#5E4FA2"],
        [0.44, "#FEE08B"],
        [0.56, "#FDAE61"],
        [0.67, "#F46D43"],
        [0.78, "#D53E4F"],
        [1.00, "#9E0142"]
    ]
except Exception:
    HAS_PLOTLY = False

# ---------------------------
# 0) Page / thème / palette
# ---------------------------
# Configuration de la page Streamlit et titre. layout="wide" donne un rendu type "dashboard".
st.set_page_config(page_title="Tableau d'émissions — Totaux & Stocks", layout="wide")
# Ce titre est spécifique au domaine d'exemple (élevage). Changez-le en clonant le modèle.
st.title("Tableau d'émissions — Exemple de modèle : Élevage (émissions & stocks)")

# Chemin vers le CSV préparé (format long). Pour votre thématique, mettez à jour ce chemin.
# Le fichier préparé doit respecter le schéma documenté pour que toute la logique UI fonctionne.
DEFAULT_PREPARED = r"\1_Donnees\livestock_PREPARED_long.csv"

# Options de région affichées à l'utilisateur. En interne, on mappe chaque libellé à la colonne
# booléenne correspondante dans le dataset. Votre prétraitement doit calculer ces booléens.
REGION_OPTIONS = ["Europe", "UE", "UE/EEE+R.-Uni"]
FLAG_MAP = {"Europe":"region_europe","UE":"region_EU","UE/EEE+R.-Uni":"region_EUEEAUK"}

# Mini palette corporate utilisée dans l'appli (fonds, textes, accents). Adaptez à votre charte.
CORP = {
    "bg":      "#f5f0e6",
    "panel":   "#e7dfcf",
    "text":    "#2e2b26",
    "accent":  "#6b8e23",
    "accent2": "#8f9779",
    "brown":   "#8b6b4a",
}

# Injection CSS légère pour harmoniser les widgets Streamlit avec la charte maison.
st.markdown(f"""
<style>
.stApp {{ background-color: {CORP["bg"]}; color: {CORP["text"]}; }}
section[data-testid="stSidebar"] > div:first-child {{ background-color: {CORP["panel"]} !important; }}
.stButton button, .stDownloadButton button {{ background-color: {CORP["accent"]} !important; color: white !important; border: 0 !important; border-radius: 10px !important; }}
.stButton button:hover, .stDownloadButton button:hover {{ filter: brightness(0.95); }}
.stTabs [role="tablist"] button[role="tab"] {{ color: {CORP["text"]}; }}
.stTabs [role="tablist"] button[aria-selected="true"] {{ border-bottom: 3px solid {CORP["accent"]}; }}
.block-container {{ background: transparent; }}
label, .stSelectbox label, .stRadio label {{ color: {CORP["text"]} !important; }}
</style>
""", unsafe_allow_html=True)

# Thème Altair (cohérence des courbes et du camembert). On l'enregistre puis on l'active.
ALT_CATEGORY = ["#9E0142","#D53E4F","#F46D43","#FDAE61","#FEE08B","#E6F598","#ABDDA4","#66C2A5","#3288BD","#5E4FA2"]*4

def _corp_altair_theme():
    return {
        "config": {
            "range": {"category": ALT_CATEGORY},
            "view": {"stroke": "transparent"},
            "axis": {"labelColor": CORP["text"], "titleColor": CORP["text"]},
            "legend": {"labelColor": CORP["text"], "titleColor": CORP["text"]},
            "title": {"color": CORP["text"]},
            "mark": {"strokeWidth": 2},
        }
    }

alt.themes.register("corp", _corp_altair_theme)
alt.themes.enable("corp")

# Convertit les codes de métrique en libellés lisibles pour l'axe Y.
# Ajoutez d'autres métriques ici si nécessaire.
def metric_unit_label(metric: str) -> str:
    if metric == "Total_CO2e": return "Total (kt CO₂e)"
    if metric == "Stocks":     return "Effectif (têtes)"
    return metric

# ---------------------------
# 1) Chargement des données
# ---------------------------
# On met en cache le chargement pour accélérer les interactions. La fonction valide aussi le schéma
# et limite l'appli aux deux métriques prévues par ce modèle.
@st.cache_data
def load_prepared(path: Path) -> pd.DataFrame:
    """
    Charge le CSV préparé (format long).

    Colonnes attendues
    ------------------
    - Area, Item, Year (int), Metric, Value
    - item_kind (catégories : 'All' | 'aggregated' | 'atomic')
    - drapeaux de région : region_europe, region_EU, region_EUEEAUK
    """
    df = pd.read_csv(path)

    # Validation des colonnes minimales ; message explicite si manquantes.
    need = {"Area","Item","Year","Metric","Value","item_kind",
            "region_europe","region_EU","region_EUEEAUK"}
    miss = need.difference(df.columns)
    if miss:
        st.error(f"Colonnes manquantes dans le CSV préparé : {', '.join(sorted(miss))}"); st.stop()

    # On ne conserve que les métriques qui nous intéresse.
    df = df[df["Metric"].isin(["Total_CO2e","Stocks"])].copy()
    # item_kind en texte pour éviter des soucis lors des normalisations.
    df["item_kind"] = df["item_kind"].astype(str)
    return df

# Lecture depuis le chemin par défaut ou via un upload interactif.
path = Path(DEFAULT_PREPARED)
if not path.exists():
    st.warning(f"CSV préparé introuvable :\n{path}\nTéléversez-le ci-dessous ou mettez à jour DEFAULT_PREPARED.")
    uploaded = st.file_uploader("Téléverser le CSV préparé", type=["csv"])
    if uploaded is None: st.stop()
    df = pd.read_csv(uploaded)
    df = df[df["Metric"].isin(["Total_CO2e","Stocks"])].copy()
else:
    df = load_prepared(path)

# Plage d'années disponible et valeurs par défaut des curseurs.
year_min, year_max = int(df["Year"].min()), int(df["Year"].max())
DEFAULT_START = max(1992, year_min)
DEFAULT_END   = min(2022, year_max)

# Normalise item_kind vers les trois valeurs canoniques utilisées par l'UI.
def normalize_kind_value(v: str) -> str:
    s = str(v).strip().lower()
    if s in {"all","all animals","all_animals"}: return "All"
    if s in {"aggregated","aggregate"}: return "aggregated"
    return "atomic"

# ---------------------------
# 2) Onglets
# ---------------------------
# Trois onglets :
#  - Tendances temporelles : courbe d'une métrique dans le temps par pays ou total régional
#  - Composition : camembert des groupes agrégés pour une année
#  - Carte : choroplèthe Total_CO2e pour l'Europe (groupe All)
# Réutilisez ces motifs en clonant pour une autre thématique.
tab_ts, tab_pie, tab_map = st.tabs(["Tendances temporelles", "Composition", "Carte"])

# =========================
# Onglet : Tendances temporelles
# =========================
# Ce que montre cet onglet
# ------------------------
# Courbes interactives d'une métrique (Total_CO2e ou Stocks) sur une plage d'années.
# Deux modes :
#   • Totaux régionaux (calculés à partir des pays via les booléens régionaux), ou
#   • Pays individuels (Top 10 d'une région ou sélection personnalisée).
with tab_ts:
    # --- Contrôles latéraux : métrique et période --------------------------------
    with st.sidebar:
        st.header("Métrique & période")
        metric = st.selectbox("Métrique", ["Total_CO2e","Stocks"], index=0)
        year_range = st.slider(
            "Plage d'années",
            min_value=year_min,
            max_value=year_max,
            value=(DEFAULT_START, DEFAULT_END),
            step=1,
        )

    # --- Regroupement d'items (All / aggregated / atomic) ------------------------
    kinds_present = sorted({normalize_kind_value(v) for v in df["item_kind"].unique()})
    kind_label_to_value = {"Tous": "All", "Agrégés": "aggregated", "Atomiques": "atomic"}
    default_kind_label = (
        "Tous" if "All" in kinds_present else ("Agrégés" if "aggregated" in kinds_present else "Atomiques")
    )

    with st.sidebar:
        st.header("Groupe d'items")
        kind_label = st.radio(
            "Choisir un groupe",
            ["Tous","Agrégés","Atomiques"],
            index=["Tous","Agrégés","Atomiques"].index(default_kind_label)
        )
    kind_value = kind_label_to_value[kind_label]

    # Liste des items disponibles pour le groupe choisi. Pour "Tous", on force une sélection unique.
    subset = df[df["item_kind"].apply(lambda x: normalize_kind_value(x) == kind_value)]
    items_all = sorted(subset["Item"].dropna().unique().tolist())

    ITEMS_KEY = "items_template_multiselect"
    if ITEMS_KEY not in st.session_state:
        st.session_state[ITEMS_KEY] = (items_all[:1] if kind_value=="All" else items_all)

    if st.session_state.get("last_kind_value") != kind_value:
        st.session_state[ITEMS_KEY] = (items_all[:1] if kind_value=="All" else items_all)
    st.session_state["last_kind_value"] = kind_value

    valides = [d for d in st.session_state[ITEMS_KEY] if d in items_all]
    if not valides:
        valides = (items_all[:1] if kind_value=="All" else items_all)
    st.session_state[ITEMS_KEY] = valides

    st.write(f"**Items — {kind_label}**")
    c1,c2,c3 = st.columns(3)
    with c1:
        if st.button("Tout sélectionner"):
            st.session_state[ITEMS_KEY] = (items_all[:1] if kind_value=="All" else items_all)
    with c2:
        if st.button("Effacer"):
            st.session_state[ITEMS_KEY] = []
    with c3:
        if kind_value=="All":
            st.caption("‘Tous’ est exclusif par conception")

    items = st.multiselect(
        "",
        options=items_all,
        default=st.session_state[ITEMS_KEY],
        key=ITEMS_KEY,
        max_selections=(1 if kind_value=="All" else None)
    )
    if not items:
        st.info("Sélectionnez au moins un item."); st.stop()

    # --- Mode d'affichage : total régional vs pays --------------------------------
    with st.sidebar:
        st.header("Mode d'affichage")
        show_region = st.checkbox("Afficher un total régional au lieu des pays", value=False)
        region_choice = st.selectbox("Région", REGION_OPTIONS, index=0, disabled=not show_region)

    # Prépare le dataframe pour le tracé : filtre métrique, période, item_kind et items choisis.
    base = df[(df["Metric"]==metric) & (df["Year"]>=year_range[0]) & (df["Year"]<=year_range[1])]
    base = base[base["item_kind"].apply(lambda x: normalize_kind_value(x) == kind_value)]
    base = base[base["Item"].isin(items)]
    if base.empty: st.info("Aucune donnée pour ces filtres."); st.stop()

    if show_region:
        # Calcule les totaux régionaux à partir des booléens de région. On élimine les lignes "(group total)".
        flag_col = FLAG_MAP[region_choice]
        sub = base[base[flag_col] & ~base["Area"].str.contains("(group total)", case=False, na=False)].copy()
        if sub.empty:
            st.info(f"Aucun pays étiqueté pour la région : {region_choice}."); st.stop()
        totals = (
            sub.groupby(["Year"], as_index=False)["Value"].sum()
               .assign(Area=region_choice)[["Area","Year","Value"]]
               .rename(columns={"Value":"SeriesValue"})
        )
    else:
        # Mode pays :
        #  - Présélection (Top 10) issue d'un groupe régional (option ‘Ajouter la Suisse’)
        #  - Personnalisé : multisélection jusqu'à 12 pays
        with st.sidebar:
            st.header("Pays")
            mode = st.radio("Mode de sélection des pays", ["Présélection (Top 10)", "Personnalisé (au choix)"])
            add_ch = False
            preset_choice = None
            available_countries = sorted(
                base[~base["Area"].str.contains("(group total)", case=False, na=False)]["Area"].dropna().unique().tolist()
            )
            if mode == "Présélection (Top 10)":
                preset_choice = st.selectbox("Groupe présélectionné", ["Europe","UE","UE/EEE+R.-Uni"], index=0)
                add_ch = st.checkbox("Ajouter la Suisse 🇨🇭", value=False)
            else:
                selected_countries = st.multiselect("Pays (max 12)", options=available_countries, max_selections=12)

        sub = base.copy()
        if mode == "Présélection (Top 10)":
            flag_col = FLAG_MAP[preset_choice]
            pool = sorted(sub.loc[sub[flag_col] & ~sub["Area"].str.contains("(group total)", case=False, na=False), "Area"].unique().tolist())
            latest_year = sub["Year"].max()
            latest = sub[(sub["Year"]==latest_year) & (sub["Area"].isin(pool))]
            ranked = (
                latest.groupby("Area", as_index=False)["Value"].sum()
                      .sort_values("Value", ascending=False)["Area"].tolist()
            )
            keep = ranked[:10]
            if add_ch and "Switzerland" in pool and "Switzerland" not in keep:
                keep.append("Switzerland")
        else:
            keep = selected_countries if 'selected_countries' in locals() and selected_countries else []

        if keep: sub = sub[sub["Area"].isin(keep)]
        if sub.empty: st.info("Aucune donnée après sélection des pays."); st.stop()
        totals = sub.groupby(["Area","Year"], as_index=False)["Value"].sum().rename(columns={"Value":"SeriesValue"})

    # --- Graphique ----------------------------------------------------------------
    y_label = metric_unit_label(metric)
    subtitle = f"{y_label} — {year_range[0]}–{year_range[1]}"
    if show_region: subtitle += f" — {region_choice}"
    st.subheader(subtitle); st.caption(f"Groupe : {kind_label}")

    # Ordre de légende : par valeur de la dernière année.
    order_latest = (
        totals[totals["Year"]==totals["Year"].max()].sort_values("SeriesValue", ascending=False)["Area"].tolist()
    )
    chart = (
        alt.Chart(totals)
           .mark_line(point=True)
           .encode(
               x=alt.X("Year:O", title="Année"),
               y=alt.Y("SeriesValue:Q", title=y_label),
               color=alt.Color("Area:N", sort=order_latest, legend=alt.Legend(title="Région" if show_region else "Pays")),
               tooltip=[
                   alt.Tooltip("Area:N", title="Région" if show_region else "Pays"),
                   alt.Tooltip("Year:O", title="Année"),
                   alt.Tooltip("SeriesValue:Q", title=y_label, format=",.0f"),
               ],
           )
           .properties(height=520)
    )
    st.altair_chart(chart, use_container_width=True)

    # Export CSV de la série agrégée.
    csv_bytes = totals.to_csv(index=False).encode("utf-8")
    fname = f"series_temporelles_{metric}_{kind_value}_{year_range[0]}_{year_range[1]}"
    fname += f"_{region_choice}_REGION.csv" if show_region else ".csv"
    st.download_button("Télécharger la série en CSV", data=csv_bytes, file_name=fname, mime="text/csv")

# =========================
# Onglet : Composition (camembert)
# =========================
# Ce que montre cet onglet
# ------------------------
# La composition (parts) de Total_CO2e par groupes agrégés pour **une année** donnée.
# Répond à : « qui contribue et combien dans la zone choisie ? »
with tab_pie:
    st.subheader("Parts par groupe agrégé (camembert)")
    st.caption("Choisissez une zone et une année. La métrique est figée à Total_CO2e dans ce modèle.")

    metric_pie = "Total_CO2e"
    year_pie = st.slider("Année du camembert", min_value=year_min, max_value=year_max, value=min(2022, year_max), step=1)

    # On limite à item_kind == aggregated pour garder un nombre de parts lisible.
    agg = df[(df["item_kind"].apply(lambda x: str(x).strip().lower() in {"aggregated","aggregate"})) &
             (df["Metric"]==metric_pie) & (df["Year"]==year_pie)].copy()
    if agg.empty:
        st.info("Aucune ligne agrégée pour cette année."); st.stop()

    # Sélection : régions calculées puis pays (on exclut les anciennes lignes ‘(group total)’).
    areas = sorted(agg["Area"].dropna().unique().tolist())
    countries = [a for a in areas if "group total" not in str(a).lower()]
    area_choice = st.selectbox("Choisir une zone (région ou pays)", ["Europe","UE","UE/EEE+R.-Uni"] + countries, index=0)

    # Calcul des parts selon le type de zone choisi.
    if area_choice in ["Europe","UE","UE/EEE+R.-Uni"]:
        flag_col = FLAG_MAP[area_choice]
        pie_df = (
            agg[agg[flag_col] & ~agg["Area"].str.contains("(group total)", case=False, na=False)][["Item","Value"]]
               .groupby("Item", as_index=False)["Value"].sum()
        )
        title_area = area_choice
    else:
        pie_df = agg[agg["Area"]==area_choice][["Item","Value"]].groupby("Item", as_index=False)["Value"].sum()
        title_area = area_choice

    # Vérification : somme > 0 pour tracer.
    total_val = float(pie_df["Value"].sum()) if not pie_df.empty else 0.0
    if total_val <= 0 or pie_df.empty:
        st.info("Aucune valeur positive à tracer pour cette sélection."); st.stop()

    # Calcul des parts — arrondis uniquement pour l'affichage.
    pie_df["Share"] = pie_df["Value"] / total_val
    pie_df["Part (%)"] = (pie_df["Share"] * 100).round(1)
    pie_df_display = pie_df[["Item","Value","Part (%)"]].sort_values("Value", ascending=False)
    pie_df_display = pie_df_display.rename(columns={"Value": "Valeur (kt CO₂e)"})
    pie_df_display["Valeur (kt CO₂e)"] = pie_df_display["Valeur (kt CO₂e)"].round(0)

    # Camembert Altair.
    pie = (
        alt.Chart(pie_df)
           .mark_arc(outerRadius=160)
           .encode(
               theta=alt.Theta(field="Value", type="quantitative", stack=True),
               color=alt.Color(field="Item", type="nominal", scale=alt.Scale(range=ALT_CATEGORY[:12]), legend=alt.Legend(title="Groupe agrégé")),
               tooltip=[
                   alt.Tooltip("Item:N", title="Groupe"),
                   alt.Tooltip("Value:Q", title="Valeur (kt CO₂e)", format=",.0f"),
                   alt.Tooltip("Share:Q", title="Part", format=".1%"),
               ],
           )
           .properties(width=520, height=520, title=f"{metric_unit_label(metric_pie)} — {title_area} — {year_pie}")
    )
    st.altair_chart(pie, use_container_width=False)

    # Tableau et export.
    st.write("Données du camembert :")
    st.dataframe(pie_df_display, use_container_width=True)
    st.download_button(
        "Télécharger les données du camembert (CSV)",
        data=pie_df_display.to_csv(index=False).encode("utf-8"),
        file_name=f"camembert_{metric_pie}_{title_area.replace(' ','_')}_{year_pie}.csv",
        mime="text/csv",
    )

# =========================
# Onglet : Carte (Total_CO2e uniquement)
# =========================
# Ce que montre cet onglet
# ------------------------
# Une choroplèthe Europe du Total_CO2e pour le groupe "All" sur une année choisie.
with tab_map:
    st.subheader("Carte des totaux — Europe (groupe ‘All’ uniquement)")
    year_map = st.slider("Année de la carte", min_value=year_min, max_value=year_max, value=min(2022, year_max), step=1)
    metric_map = "Total_CO2e"

    # Si Plotly n'est pas installé, message clair et arrêt de cet onglet uniquement.
    if not HAS_PLOTLY:
        st.error("Plotly n'est pas installé. Dans un terminal, exécutez :\n\n  py -m pip install plotly\n\nPuis relancez l'application.")
        st.stop()

    # La carte utilise item_kind == 'All' pour éviter les doubles comptes. On enlève ‘(group total)’
    # et on restreint aux pays étiquetés Europe via region_europe == True.
    sub_all = df[df["item_kind"].apply(lambda v: str(v).strip().lower() in {"all","all animals","all_animals"})]
    sub = sub_all[(sub_all["Metric"]==metric_map) & (sub_all["Year"]==year_map)].copy()
    sub = sub[~sub["Area"].str.contains("(group total)", case=False, na=False)].copy()

    sub = sub[sub["region_europe"]==True]

    map_df = sub.groupby(["Area"], as_index=False)["Value"].sum()

    # Normalisation de quelques noms de pays pour correspondre aux attentes Plotly.
    name_fix = {"UK": "United Kingdom", "Russia": "Russian Federation"}
    map_df["Area"] = map_df["Area"].replace(name_fix)

    label = "Total (kt CO₂e)"
    fig = px.choropleth(
        map_df,
        locations="Area",
        locationmode="country names",
        color="Value",
        scope="europe",
        color_continuous_scale=CORP_SCALE,
        labels={"Value": label, "Area": "Pays"},
        title=f"{label} — Europe — {year_map}",
    )
    fig.update_layout(
        margin=dict(l=10,r=10,t=50,b=10),
        paper_bgcolor=CORP["bg"],
        plot_bgcolor=CORP["panel"],
        font_color=CORP["text"],
    )
    st.plotly_chart(fig, use_container_width=True)

    # Valeurs cartographiées + export CSV.
    st.write("Valeurs cartographiées :")
    map_df_display = map_df.rename(columns={"Value": "Valeur (kt CO₂e)"})
    map_df_display["Valeur (kt CO₂e)"] = map_df_display["Valeur (kt CO₂e)"].round(0)
    st.dataframe(map_df_display.sort_values("Valeur (kt CO₂e)", ascending=False), use_container_width=True)
    st.download_button(
        "Télécharger les données de la carte (CSV)",
        data=map_df_display.to_csv(index=False).encode("utf-8"),
        file_name=f"carte_Total_CO2e_{year_map}.csv",
        mime="text/csv",
    )
