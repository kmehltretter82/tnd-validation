import TNDLib.Matching.Cardinality

namespace TNDLib.Matching.Tests

example : findEmptyReceiver (fun _ : Fin 0 => none) = none := rfl

example : findEmptyReceiver (fun _ : Fin 1 => none) = some 0 := rfl

example : findEmptyReceiver (fun receiver : Fin 2 => some receiver) = none := rfl

example : findEmptyReceiver
    (fun receiver : Fin 2 => if receiver.val = 0 then some (0 : Fin 2) else none) = some 1 := rfl

#print axioms TNDLib.Matching.existsEmptyReceiverOfFree
#print axioms TNDLib.Matching.findEmptyReceiver_none_iff
#print axioms TNDLib.Matching.findEmptyReceiver_some
#print axioms TNDLib.Matching.findEmptyReceiver_ne_none_of_free

end TNDLib.Matching.Tests
