"""Recipe subsystem dataclasses (sec10 §10.3).

Python types describing recipe manifests, install plans, install
results, and inspection / diff reports. No behavior — :class:`RecipeService`
(``hippo.core.recipe_service``) owns the verbs.

Re-exported here so callers import from one place:

    from hippo.core.recipe import RecipeManifest, RecipeRef, InstalledRecipe
"""

from __future__ import annotations

from hippo.core.recipe.dataclasses import (
    ImportPlan,
    ImportResult,
    InstalledRecipe,
    RecipeAuthor,
    RecipeDiff,
    RecipeManifest,
    RecipeRef,
    RecipeReport,
    RecipeRequires,
)

__all__ = [
    "ImportPlan",
    "ImportResult",
    "InstalledRecipe",
    "RecipeAuthor",
    "RecipeDiff",
    "RecipeManifest",
    "RecipeRef",
    "RecipeReport",
    "RecipeRequires",
]
