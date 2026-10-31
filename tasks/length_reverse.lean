import TNDLib

universe u

namespace TNDTask

theorem lengthReverse {α : Type u} (l : List α) : l.reverse.length = l.length :=
  List.length_reverse

end TNDTask
