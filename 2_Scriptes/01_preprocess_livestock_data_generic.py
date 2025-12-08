#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prétraitement de jeux de données « élevage » — v4g (version commentée FR)
=======================================================================


But du script
-------------
Transformer un CSV « large » (colonnes d’années Y2010, Y2011, …) contenant des
lignes par pays (`Area`), item (`Item`) et élément (`Element`) en un **CSV long**
avec colonnes : `Area, Item, Year, Metric, Value` + métadonnées (item_kind, flags régionaux).


Points clés / garde-fous (v4g)
------------------------------
- **Éclatement du libellé générique « Cattle »** en « Cattle, dairy » et « Cattle, non-dairy »
**uniquement** lorsque, pour un couple (Area, Year), **aucune** ligne atomique bovins n’existe déjà.
→ évite de dupliquer des lignes si l’input contient déjà « Cattle, dairy » / « Cattle, non-dairy ».
- **LSU (Livestock Units)** calculé à partir des `Stocks` via des poids par espèce, puis **regroupé**
par (Area, Item, Year) pour supprimer d’éventuels doublons amont.
- **Normalisations** : libellés bovins (priorité au non-laitier), drapeaux régionaux (Europe/UE/UE+EEE+R.-Uni),
classification `item_kind` (All / aggregated / atomic).


Sorties produites
-----------------
- `Stocks` (tel quel)
- `CH4_CO2e`, `N2O_CO2e` (conversion via PRG/GWP)
- `Total_CO2e` (= CH4_CO2e + N2O_CO2e)
- `LSU` (à partir de Stocks * poids LSU)


Paramètres CLI importants
-------------------------
--input : Chemin du CSV brut (doit contenir Area, Item, Element + années Y...)
--output : Chemin du CSV de sortie (par défaut, dossier de l’input)
--gwp : Choix des PRG (AR4|AR5|AR6_NOCCF|AR6_CCF)
--split-cattle : true/false — autoriser l’éclatement de « Cattle » lorsque possible
--dairy-share : % attribué au laitier lors de l’éclatement (ex : 35 => 35%)
--only-livestock-total : true/false — pour CH4/N2O, ne garder que les lignes « Livestock total »
"""


from __future__ import annotations
import argparse, re, sys
from pathlib import Path
import pandas as pd


# --- Listes de référence pour classer les items -------------------------------------------------
# Ces listes servent à :
# - reconnaître le total « All » (tous animaux)
# - repérer les groupes agrégés (ex. Cattle, Poultry Birds, …)
# - repérer les items atomiques (ex. Cattle, dairy / non-dairy, Ducks, …)
ALL_ANIMALS_LIST = ["All animals","All animal","All livestock","Total animals","Animals, all"]
AGGREGATE_LIST = ["Camels and Llamas","Cattle","Mules and Asses","Poultry Birds","Sheep and Goats","Swine"]
ATOMIC_LIST = ["Asses","Buffalo","Camels","Swine, breeding","Swine, market","Turkeys",
"Cattle, dairy","Cattle, non-dairy","Chickens, broilers","Chickens, layers",
"Ducks","Goats","Horses","Sheep"]


# Items à exclure explicitement (libellés trop génériques ou vides)
EXCLUDE_ITEMS = {s.lower() for s in ["Chickens","Mules and hinnies","(blank)",""]}


# --- Groupes régionaux (utilisés pour créer des booléens par région) -----------------------------
EU = {"Austria","Belgium","Bulgaria","Croatia","Cyprus","Czechia","Czech Republic","Denmark","Estonia",
"Finland","France","Germany","Greece","Hungary","Ireland","Italy","Latvia","Lithuania","Luxembourg",
"Malta","Netherlands","Poland","Portugal","Romania","Slovakia","Slovenia","Spain","Sweden"}
EEA_PLUS_UK = EU.union({"Iceland","Liechtenstein","Norway","United Kingdom","UK"})
main()
