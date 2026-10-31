import TNDLib

universe u v

namespace TNDTask

theorem mapExists {α : Type u} {β : Type v} (f : α → β) (p : β → Prop) :
    (∃ x : α, p (f x)) → ∃ y : β, p y :=
  sorry

end TNDTask
