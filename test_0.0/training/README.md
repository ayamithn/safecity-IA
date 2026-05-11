# Entraîner SafeCity à détecter de nouvelles menaces

Ce dossier sert à entraîner un modèle YOLO personnalisé pour SafeCity AI Monitor.

## 1. Classes

Les classes sont dans `training/classes.txt` :

```text
pistol
rifle
knife
machete
baton
hammer
screwdriver
crowbar
metal_bar
threatening_tool
```

Tu peux modifier cette liste avant d'annoter ton dataset. L'ordre est important : il doit rester identique entre les labels YOLO et `classes.txt`.

## 2. Dataset

Place les images et labels ici :

```text
training/dataset/
  images/
    train/
    val/
  labels/
    train/
    val/
```

Chaque image doit avoir un fichier label du même nom :

```text
images/train/exemple_001.jpg
labels/train/exemple_001.txt
```

Format d'une ligne YOLO :

```text
class_id x_center y_center width height
```

Les coordonnées sont normalisées entre `0` et `1`.

## 3. Entraîner

Depuis la racine du projet :

```powershell
python training/train_weapon_model.py --epochs 80 --base-model yolov8s.pt
```

Pour CPU uniquement :

```powershell
python training/train_weapon_model.py --device cpu --epochs 80 --base-model yolov8s.pt
```

Le script copie automatiquement le meilleur modèle vers :

```text
models/safecity_weapons.pt
```

SafeCity le charge automatiquement au prochain démarrage.

## 4. Installer un best.pt déjà entraîné

```powershell
python training/install_best_model.py --source runs/detect/safecity_weapons/weights/best.pt
```

## 5. Lancer SafeCity avec le modèle appris

```powershell
python main.py
```

Dans le dashboard, `DÉTECTEUR MENACES` doit afficher `Custom: safecity_weapons.pt`.

## Notes importantes

- Ne mets pas seulement des images d'armes : ajoute aussi des images normales sans menace pour limiter les faux positifs.
- Mélange différents angles, distances, éclairages et qualités de caméra.
- Garde des images de validation que le modèle n'a jamais vues pendant l'entraînement.
- Le modèle reste une aide à la décision, pas une preuve automatique.
