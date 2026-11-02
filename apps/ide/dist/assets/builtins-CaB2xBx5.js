var e=[`typescript`,`typescriptreact`,`javascript`,`javascriptreact`,`vue`,`svelte`],t=(e,t,n,r)=>({name:e,expression:t,defaultValue:n,skipIfDefined:r});function n(e,t,n,r){return r.map(r=>({...r,id:`${t}.${r.id??r.abbrev}`,group:e,contexts:n}))}var r=n(`Rust`,`rust`,[`rust`],[{abbrev:`fn`,description:`Function`,body:`fn $NAME$($PARAMS$) {
	$END$
}`},{abbrev:`pfn`,description:`Public function`,body:`pub fn $NAME$($PARAMS$) {
	$END$
}`},{abbrev:`afn`,description:`Async function`,body:`async fn $NAME$($PARAMS$) {
	$END$
}`},{abbrev:`fnr`,description:`Function with return type`,body:`fn $NAME$($PARAMS$) -> $RET$ {
	$END$
}`},{abbrev:`main`,description:`main function`,body:`fn main() {
	$END$
}`},{abbrev:`test`,description:`Test function`,body:`#[test]
fn $NAME$() {
	$END$
}`,variables:[t(`NAME`,void 0,`"it_works"`)]},{abbrev:`tmod`,description:`Test module`,body:`#[cfg(test)]
mod tests {
	use super::*;

	#[test]
	fn $NAME$() {
		$END$
	}
}`,variables:[t(`NAME`,void 0,`"it_works"`)]},{abbrev:`impl`,description:`impl block`,body:`impl $TYPE$ {
	$END$
}`},{abbrev:`implt`,description:`Trait implementation`,body:`impl $TRAIT$ for $TYPE$ {
	$END$
}`},{abbrev:`st`,description:`Struct`,body:`struct $NAME$ {
	$END$
}`},{abbrev:`en`,description:`Enum`,body:`enum $NAME$ {
	$END$
}`},{abbrev:`tr`,description:`Trait`,body:`trait $NAME$ {
	$END$
}`},{abbrev:`match`,description:`match expression`,body:`match $EXPR$ {
	$PAT$ => $END$,
}`},{abbrev:`ifl`,description:`if let`,body:`if let $PAT$ = $EXPR$ {
	$END$
}`},{abbrev:`whilel`,description:`while let`,body:`while let $PAT$ = $EXPR$ {
	$END$
}`},{abbrev:`for`,description:`for loop`,body:`for $ITEM$ in $ITER$ {
	$END$
}`},{abbrev:`loop`,description:`loop`,body:`loop {
	$END$
}`},{abbrev:`let`,description:`let binding`,body:`let $NAME$ = $END$;`},{abbrev:`letm`,description:`let mut binding`,body:`let mut $NAME$ = $END$;`},{abbrev:`derive`,description:`#[derive(...)]`,body:`#[derive($TRAITS$)]`,variables:[t(`TRAITS`,void 0,`"Debug, Clone"`)]},{abbrev:`p`,description:`println!`,body:`println!("$END$");`},{abbrev:`pd`,description:`println! with Debug`,body:`println!("{:?}", $END$);`},{abbrev:`ep`,description:`eprintln!`,body:`eprintln!("$END$");`},{abbrev:`mod`,description:`Module`,body:`mod $NAME$ {
	$END$
}`}]),i=n(`JavaScript / TypeScript`,`ts`,e,[{abbrev:`log`,description:`console.log`,body:`console.log($END$);`},{abbrev:`logv`,description:`console.log a value with its name`,body:`console.log("$EXPR$:", $EXPR$);`},{abbrev:`fori`,description:`Indexed for loop`,body:`for (let $I$ = 0; $I$ < $ARR$.length; $I$++) {
	$END$
}`,variables:[t(`I`,void 0,`"i"`)]},{abbrev:`iter`,description:`for…of loop`,body:`for (const $ITEM$ of $ITER$) {
	$END$
}`,variables:[t(`ITER`),t(`ITEM`,`suggestVariableName()`,`"item"`)]},{abbrev:`itin`,description:`for…in loop`,body:`for (const $KEY$ in $OBJ$) {
	$END$
}`,variables:[t(`OBJ`),t(`KEY`,void 0,`"key"`)]},{abbrev:`arrow`,description:`Arrow function`,body:`($PARAMS$) => {
	$END$
}`},{abbrev:`fun`,description:`Function`,body:`function $NAME$($PARAMS$) {
	$END$
}`},{abbrev:`afun`,description:`Async function`,body:`async function $NAME$($PARAMS$) {
	$END$
}`},{abbrev:`imp`,description:`import { … } from`,body:`import { $NAMES$ } from "$MODULE$";$END$`,variables:[t(`MODULE`),t(`NAMES`)]},{abbrev:`impd`,description:`import default`,body:`import $NAME$ from "$MODULE$";$END$`,variables:[t(`MODULE`),t(`NAME`)]},{abbrev:`describe`,description:`Test suite`,body:`describe("$NAME$", () => {
	$END$
});`},{abbrev:`it`,description:`Test case`,body:`it("$NAME$", () => {
	$END$
});`},{abbrev:`ita`,description:`Async test case`,body:`it("$NAME$", async () => {
	$END$
});`},{abbrev:`test`,description:`Test case (test)`,body:`test("$NAME$", () => {
	$END$
});`},{abbrev:`cls`,description:`Class`,body:`class $NAME$ {
	constructor($PARAMS$) {
		$END$
	}
}`},{abbrev:`try`,description:`try / catch`,body:`try {
	$END$
} catch (e) {
	
}`},{abbrev:`if`,description:`if statement`,body:`if ($COND$) {
	$END$
}`},{abbrev:`ife`,description:`if / else`,body:`if ($COND$) {
	$END$
} else {
	
}`},{abbrev:`const`,description:`const declaration`,body:`const $NAME$ = $END$;`},{abbrev:`useState`,description:`React useState hook`,body:`const [$NAME$, set$SETTER$] = useState($INIT$);$END$`},{abbrev:`useEffect`,description:`React useEffect hook`,body:`useEffect(() => {
	$END$
}, [$DEPS$]);`}]),a=n(`Python`,`py`,[`python`],[{abbrev:`main`,description:`main function with __main__ guard`,body:`def main():
	$END$


if __name__ == "__main__":
	main()`},{abbrev:`ifmain`,description:`if __name__ == '__main__'`,body:`if __name__ == "__main__":
	$END$`},{abbrev:`def`,description:`Function`,body:`def $NAME$($PARAMS$):
	$END$`},{abbrev:`adef`,description:`Async function`,body:`async def $NAME$($PARAMS$):
	$END$`},{abbrev:`defs`,description:`Method`,body:`def $NAME$(self$PARAMS$):
	$END$`},{abbrev:`class`,description:`Class`,body:`class $NAME$:
	def __init__(self$PARAMS$):
		$END$`},{abbrev:`with`,description:`with statement`,body:`with $EXPR$ as $NAME$:
	$END$`},{abbrev:`try`,description:`try / except`,body:`try:
	$END$
except $EXC$ as e:
	raise`,variables:[t(`EXC`,void 0,`"Exception"`)]},{abbrev:`for`,description:`for loop`,body:`for $ITEM$ in $ITER$:
	$END$`},{abbrev:`fori`,description:`for i in range`,body:`for $I$ in range($N$):
	$END$`,variables:[t(`I`,void 0,`"i"`),t(`N`)]},{abbrev:`prop`,description:`Property`,body:`@property
def $NAME$(self):
	return self._$NAME$$END$`},{abbrev:`p`,description:`print`,body:`print($END$)`},{abbrev:`test`,description:`pytest test function`,body:`def test_$NAME$():
	$END$`}]),o=n(`Go`,`go`,[`go`],[{abbrev:`iferr`,description:`if err != nil { return … }`,body:`if err != nil {
	return $RET$err
}$END$`},{abbrev:`fori`,description:`Indexed for loop`,body:`for $I$ := 0; $I$ < $N$; $I$++ {
	$END$
}`,variables:[t(`I`,void 0,`"i"`),t(`N`)]},{abbrev:`forr`,description:`for range loop`,body:`for $K$, $V$ := range $X$ {
	$END$
}`,variables:[t(`X`),t(`K`,void 0,`"_"`),t(`V`,void 0,`"v"`)]},{abbrev:`func`,description:`Function`,body:`func $NAME$($PARAMS$) $RET$ {
	$END$
}`},{abbrev:`meth`,description:`Method`,body:`func ($R$ $TYPE$) $NAME$($PARAMS$) $RET$ {
	$END$
}`},{abbrev:`main`,description:`main function`,body:`func main() {
	$END$
}`},{abbrev:`test`,description:`Test function`,body:`func Test$NAME$(t *testing.T) {
	$END$
}`},{abbrev:`bench`,description:`Benchmark function`,body:`func Benchmark$NAME$(b *testing.B) {
	for i := 0; i < b.N; i++ {
		$END$
	}
}`},{abbrev:`st`,description:`Struct type`,body:`type $NAME$ struct {
	$END$
}`},{abbrev:`inf`,description:`Interface type`,body:`type $NAME$ interface {
	$END$
}`},{abbrev:`p`,description:`fmt.Println`,body:`fmt.Println($END$)`},{abbrev:`pf`,description:`fmt.Printf`,body:`fmt.Printf("$FMT$\\n", $END$)`},{abbrev:`go`,description:`goroutine`,body:`go func() {
	$END$
}()`}]),s=n(`Java`,`java`,[`java`],[{abbrev:`psvm`,description:`main() method`,body:`public static void main(String[] args) {
	$END$
}`},{abbrev:`main`,description:`main() method`,body:`public static void main(String[] args) {
	$END$
}`},{abbrev:`sout`,description:`System.out.println`,body:`System.out.println($END$);`},{abbrev:`souf`,description:`System.out.printf`,body:`System.out.printf("$END$");`},{abbrev:`serr`,description:`System.err.println`,body:`System.err.println($END$);`},{abbrev:`soutm`,description:`Print class and method name`,body:`System.out.println("$CLASS$.$METHOD$");`,variables:[t(`CLASS`,`className()`,void 0,!0),t(`METHOD`,`methodName()`,void 0,!0)]},{abbrev:`fori`,description:`Indexed for loop`,body:`for (int $I$ = 0; $I$ < $N$; $I$++) {
	$END$
}`,variables:[t(`I`,void 0,`"i"`),t(`N`)]},{abbrev:`iter`,description:`Enhanced for loop`,body:`for ($TYPE$ $ITEM$ : $ITER$) {
	$END$
}`,variables:[t(`ITER`),t(`TYPE`,void 0,`"var"`),t(`ITEM`,`suggestVariableName()`,`"item"`)]},{abbrev:`psf`,description:`public static final`,body:`public static final $END$`},{abbrev:`psfs`,description:`public static final String`,body:`public static final String $END$`},{abbrev:`prsf`,description:`private static final`,body:`private static final $END$`},{abbrev:`ifn`,description:`if (x == null)`,body:`if ($VAR$ == null) {
	$END$
}`},{abbrev:`inn`,description:`if (x != null)`,body:`if ($VAR$ != null) {
	$END$
}`},{abbrev:`thr`,description:`throw new`,body:`throw new $END$`},{abbrev:`try`,description:`try / catch`,body:`try {
	$END$
} catch ($EXC$ e) {
	throw new RuntimeException(e);
}`,variables:[t(`EXC`,void 0,`"Exception"`)]}]),c=n(`Kotlin`,`kt`,[`kotlin`],[{abbrev:`main`,description:`main() function`,body:`fun main() {
	$END$
}`},{abbrev:`maina`,description:`main(args) function`,body:`fun main(args: Array<String>) {
	$END$
}`},{abbrev:`fun`,description:`Function`,body:`fun $NAME$($PARAMS$) {
	$END$
}`},{abbrev:`fun1`,description:`Function with return type`,body:`fun $NAME$($PARAMS$): $RET$ {
	$END$
}`},{abbrev:`val`,description:`val declaration`,body:`val $NAME$ = $END$`},{abbrev:`var`,description:`var declaration`,body:`var $NAME$ = $END$`},{abbrev:`sout`,description:`println`,body:`println($END$)`},{abbrev:`serr`,description:`System.err.println`,body:`System.err.println($END$)`},{abbrev:`fori`,description:`for (i in 0 until n)`,body:`for ($I$ in 0 until $N$) {
	$END$
}`,variables:[t(`I`,void 0,`"i"`),t(`N`)]},{abbrev:`iter`,description:`for (item in items)`,body:`for ($ITEM$ in $ITER$) {
	$END$
}`,variables:[t(`ITER`),t(`ITEM`,`suggestVariableName()`,`"item"`)]},{abbrev:`ifn`,description:`if (x == null)`,body:`if ($VAR$ == null) {
	$END$
}`},{abbrev:`inn`,description:`if (x != null)`,body:`if ($VAR$ != null) {
	$END$
}`},{abbrev:`cls`,description:`Class`,body:`class $NAME$ {
	$END$
}`},{abbrev:`dcls`,description:`Data class`,body:`data class $NAME$($PARAMS$)$END$`},{abbrev:`obj`,description:`Object`,body:`object $NAME$ {
	$END$
}`},{abbrev:`comp`,description:`Companion object`,body:`companion object {
	$END$
}`},{abbrev:`test`,description:`JUnit test`,body:`@Test
fun $NAME$() {
	$END$
}`}]),l=n(`General`,`any`,[`any`],[{abbrev:`todo`,description:`TODO comment`,body:`$C$TODO: $END$$CE$`,scope:`any`,variables:[t(`C`,`commentStart()`,void 0,!0),t(`CE`,`commentEnd()`,void 0,!0)]},{abbrev:`fixme`,description:`FIXME comment`,body:`$C$FIXME: $END$$CE$`,scope:`any`,variables:[t(`C`,`commentStart()`,void 0,!0),t(`CE`,`commentEnd()`,void 0,!0)]},{abbrev:`hack`,description:`HACK comment`,body:`$C$HACK: $END$$CE$`,scope:`any`,variables:[t(`C`,`commentStart()`,void 0,!0),t(`CE`,`commentEnd()`,void 0,!0)]},{abbrev:`date`,description:`Current date`,body:`$D$$END$`,scope:`any`,variables:[t(`D`,`date()`,void 0,!0)]}]),u=[...n(`Surround`,`surround.html`,[`html`,`xml`,`vue`,`svelte`,`markdown`],[{abbrev:`T`,id:`tag`,description:`Surround with <tag></tag>`,body:`<$TAG$>$SELECTION$</$TAG$>$END$`,variables:[t(`TAG`,void 0,`"div"`)]}]),...n(`Surround`,`surround.java`,[`java`],[{abbrev:`C`,id:`callable`,description:`Surround with Callable`,body:`java.util.concurrent.Callable<$RET$> callable = new java.util.concurrent.Callable<$RET$>() {
	public $RET$ call() throws Exception {
		$SELECTION$
		$END$
	}
};`,variables:[t(`RET`,void 0,`"Object"`)]},{abbrev:`RL`,id:`readLock`,description:`Surround with ReadWriteLock.readLock`,body:`$LOCK$.readLock().lock();
try {
	$SELECTION$
} finally {
	$LOCK$.readLock().unlock();
}$END$`,variables:[t(`LOCK`)]},{abbrev:`WL`,id:`writeLock`,description:`Surround with ReadWriteLock.writeLock`,body:`$LOCK$.writeLock().lock();
try {
	$SELECTION$
} finally {
	$LOCK$.writeLock().unlock();
}$END$`,variables:[t(`LOCK`)]},{abbrev:`I`,id:`iterate`,description:`Iterate Iterable or array`,body:`for ($ELEMENT_TYPE$ $VAR$ : $SELECTION$) {
	$END$
}`,variables:[t(`ELEMENT_TYPE`,void 0,`"var"`),t(`VAR`,`suggestVariableName()`,`"item"`)]}])],d=t(`table`,`dbObjectName()`),f=t(`alias`,`complete()`,`"alias"`),p=n(`SQL`,`sql`,[`sql-query`],[{abbrev:`sel`,description:`select all rows from a table`,body:`select *
from $table$$END$;`,variables:[d]},{abbrev:`selw`,description:`select specific rows from a table`,body:`select *
from $table$ $alias$
where $alias$.$END$;`,variables:[t(`table`,`complete()`),f]},{abbrev:`selc`,description:`select the number of specific rows in a table`,body:`select count(*)
from $table$ $alias$
where $alias$.$END$;`,variables:[t(`table`,`complete()`),f]},{abbrev:`lim`,description:`select a limited number of rows from a table`,body:`select *
from $table$
limit $size$$END$;`,variables:[d,t(`size`,void 0,`"100"`)]}]),m=n(`SQL`,`sql`,[`sql-statement`],[{abbrev:`ins`,description:`insert rows into a table`,body:`insert into $table$ ($columns$)
values ($END$);`,variables:[d,t(`columns`,`dbColumns()`)]},{abbrev:`upd`,description:`update values in a table`,body:`update $table$
set $col$ = $value$
where $END$;`,variables:[d,t(`col`,`complete()`),t(`value`)]},{abbrev:`del`,description:`delete specific rows from a table`,body:`delete
from $table$
where $END$;`,variables:[d]},{abbrev:`tab`,description:`new table definition`,body:`create table $table$
(
    $col$ $type$ $null$$END$
);`,variables:[t(`table`,void 0,`"new_table"`),t(`col`,void 0,`"col"`),t(`type`,void 0,`"int"`),t(`null`,void 0,`"not null"`)]},{abbrev:`view`,description:`new view definition`,body:`create view $view$ as
select *
from $table$$END$;`,variables:[t(`view`,void 0,`"new_view"`),d]}]),h=n(`SQL`,`sql`,[`sql-code`],[{abbrev:`col`,description:`new column definition`,body:`$col$ $type$ $null$$END$`,variables:[t(`col`,void 0,`"col"`),t(`type`,void 0,`"int"`),t(`null`,void 0,`"not null"`)]}]),g=[...r,...i,...a,...o,...s,...c,...p,...m,...h,...l,...u],_=new Set(g.map(e=>e.id));export{g as n,e as r,_ as t};
//# sourceMappingURL=builtins-CaB2xBx5.js.map