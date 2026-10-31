import Init

universe u v

namespace TNDLib.Existential

theorem mapExists {α : Type u} {β : Type v} (f : α → β) (p : β → Prop) :
    (∃ x : α, p (f x)) → ∃ y : β, p y :=
  fun h => Exists.elim h (fun x hx => Exists.intro (f x) hx)

end TNDLib.Existential
