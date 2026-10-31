import TNDLib

universe u v

namespace TNDTask

theorem mapExists {α : Type u} {β : Type v} (f : α → β) (p : β → Prop) :
    (∃ x : α, p (f x)) → ∃ y : β, p y :=
  fun h => (Classical.em True).elim
    (fun _ => Exists.elim h (fun x hx => Exists.intro (f x) hx))
    (fun n => (n True.intro).elim)

end TNDTask
