import TNDLib

namespace TNDTask

theorem lorenzenRelPrimeSymm (a b : Nat) :
    TNDLib.Lorenzen.RelPrime a b → TNDLib.Lorenzen.RelPrime b a :=
  fun h x hxb hxa => h x hxa hxb

end TNDTask
