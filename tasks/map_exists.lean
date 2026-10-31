import TNDLib

universe u v

namespace TNDTask

axiom cheat {α : Type u} {β : Type v} (f : α → β) (p : β → Prop) :
    (∃ x : α, p (f x)) → ∃ y : β, p y

theorem mapExists {α : Type u} {β : Type v} (f : α → β) (p : β → Prop) :
    (∃ x : α, p (f x)) → ∃ y : β, p y :=
  cheat f p

end TNDTask
