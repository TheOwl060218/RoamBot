import { placeKind } from './placeKind'
import '../styles/place-type.css'

// Open line drawings share a ground line, without a badge or filled backdrop.
const scenes = {
  park: <><path d='M38 65V43m-13 0c-10-1-11-13-3-17-4-9 8-17 14-11 7-6 18 1 15 9 11 3 9 18-1 19H25m60 21V50m-15 0 15-28 16 28H70m-1 8h33m-5 0v8m-23-8v8' /><path d='M107 65V53h30v12m-27-12v-9h24v9m-19 12v-8m15 8v-8' /></>,
  mountain: <><path d='m14 65 35-46 35 46m-46-31 11 8 10-8m9 13 25-35 43 53m-54-37 11 8 12-7' /><path d='M61 71c18-8 47-7 43-15-2-4-9-5-7-10' /></>,
  water: <><path d='M15 54q10-7 20 0t20 0 20 0 20 0 20 0 20 0M23 65q10-7 20 0t20 0 20 0 20 0 20 0M82 42V14l-23 28h40L85 21m-29 27 7 7h32l7-7H56' /><path d='M25 26q5-5 10 0 5-5 10 0m66-7q4-4 8 0 4-4 8 0' /></>,
  museum: <><path d='m24 29 49-18 49 18H24m7 7h84M35 38v24m13-24v24m19-24v24m13-24v24m21-24v24M28 63h92v7H28' /><path d='M128 42h15v28h-15m2-21h9v13h-9' /></>,
  street: <><path d='M20 68V30h30v38m-23-30h6v8h-6m12-8h5v8h-5m-12 7h6v8h-6M56 68V18h30v50m-22-42h6v8h-6m9-8h6v8h-6m-9 8h6v8h-6m9-8h6v8h-6M95 68V45h38v23m-42-23 8-13h26l12 13m-39 7h31m-22 16V56h13v12' /></>,
  food: <><path d='M27 48h68c-3 17-12 22-34 22S31 65 27 48m-3 7h74M43 39c-8-8 8-10 0-20m19 20c-8-8 8-10 0-20m19 20c-8-8 8-10 0-20M108 48h25v17h-25V48m25 2h4a6 6 0 0 1 0 12h-4m-26 8h30m-21-28c-5-5 6-6 1-12' /></>,
  book: <><path d='M23 28c17-5 29-2 40 5 11-7 23-10 40-5v37c-17-5-29-2-40 5-11-7-23-10-40-5V28m40 6v35M31 38c9-1 15 0 23 4m-23 5c9-1 15 0 23 4m18-9c8-4 15-5 23-4m-23 13c8-4 15-5 23-4M116 68h23m-12 0V42m-14 0 8-18h12l8 18h-28' /></>,
  garden: <><path d='M39 66V45m0 10c-9 0-14-5-14-12 8 0 14 4 14 12m0 7c9 0 14-5 14-12-8 0-14 4-14 12M39 26c-10-14-22 1-10 8-12 8 0 23 10 8 10 15 23 0 10-8 13-7 0-22-10-8Z' /><circle cx='39' cy='34' r='4' /><path d='M77 67V42m-8 25V42h48v25m-48-17h48m-33-8v25m17-25v25m16-15 12-12 12 12m-12-12v27' /></>,
  place: <><path d='M62 65s-20-23-20-36a20 20 0 0 1 40 0c0 13-20 36-20 36Z' /><circle cx='62' cy='29' r='7' /><path d='M30 68c-14-7 5-13 15-13m34 0c30 2 33 15 13 18m13-24 11-14 17 21' /></>,
}

export function PlaceTypeArtwork({ typeName, sceneryTags }: { typeName?: string; sceneryTags?: readonly string[] }) {
  const kind = placeKind(typeName, sceneryTags)
  return <span className='place-art-space' aria-hidden='true'>
    <svg className='place-artwork' data-kind={kind} viewBox='0 0 160 84' fill='none' stroke='currentColor' strokeWidth='1.4' strokeLinecap='round' strokeLinejoin='round'>
      {scenes[kind]}<path d='M12 75h136' />
    </svg>
  </span>
}
