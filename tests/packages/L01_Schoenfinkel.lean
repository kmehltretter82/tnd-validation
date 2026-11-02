import Init

/-!
Package L01: Schönfinkel (1920/1924), typed combinators `I`, `C`, `T`, `Z`, `S`
and pointwise reductions to `C` and `S`.
-/

universe u v w

namespace TNDPackage.L01Schoenfinkel

/-- Currying of a binary function on pairs `(α × β) → γ` into `α → β → γ`. -/
def curry {α : Type u} {β : Type v} {γ : Type w} (f : α × β → γ) : α → β → γ :=
  fun a b => f (a, b)

/-- Uncurrying of a higher-order function `α → β → γ` into `(α × β) → γ`. -/
def uncurry {α : Type u} {β : Type v} {γ : Type w} (g : α → β → γ) : α × β → γ :=
  fun p => g p.1 p.2

/-- Schönfinkel's identity combinator (`Identitätsfunktion`) `I`. -/
def combI {α : Type u} (x : α) : α :=
  x

/-- Schönfinkel's constancy combinator (`Konstanzfunktion`) `C` (modern `K`). -/
def combC {α : Type u} {β : Type v} (x : α) (_ : β) : α :=
  x

/-- Schönfinkel's swap combinator (`Vertauschungsfunktion`) `T` (modern `C`). -/
def combT {α : Type u} {β : Type v} {γ : Type w} (f : α → β → γ) (y : β) (x : α) : γ :=
  f x y

/-- Schönfinkel's composition combinator (`Zusammensetzungsfunktion`) `Z` (modern `B`). -/
def combZ {α : Type u} {β : Type v} {γ : Type w} (f : β → γ) (g : α → β) (x : α) : γ :=
  f (g x)

/-- Schönfinkel's fusion combinator (`Verschmelzungsfunktion`) `S`. -/
def combS {α : Type u} {β : Type v} {γ : Type w}
    (f : α → β → γ) (g : α → β) (x : α) : γ :=
  f x (g x)

/-- Reduction of `I` to `C` and `S`: `S C (C w) x = I x`. -/
theorem schoenfinkel_I_from_CS {α : Type u} {β : Type v} (w : β) (x : α) :
    combS combC (combC (α := β) (β := α) w) x = combI x :=
  rfl

/-- Reduction of `Z` to `C` and `S`: `S (C S) C f g x = Z f g x`. -/
theorem schoenfinkel_Z_from_CS {α : Type u} {β : Type v} {γ : Type w}
    (f : β → γ) (g : α → β) (x : α) :
    combS (combC combS) combC f g x = combZ f g x :=
  rfl

/-- Reduction of `T` to `C`, `S`, and `Z`: `S (Z Z S) (C C) f y x = T f y x`. -/
theorem schoenfinkel_T_from_CSZ {α : Type u} {β : Type v} {γ : Type w}
    (f : α → β → γ) (y : β) (x : α) :
    combS (combZ combZ combS) (combC combC) f y x = combT f y x :=
  rfl

end TNDPackage.L01Schoenfinkel
