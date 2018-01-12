import { Routes, RouterModule } from '@angular/router';

import { HomeComponent } from './home/index';
import { LoginComponent } from './login/index';
import { RegisterComponent } from './register/index';
import { AuthGuard } from './_guards/index';
import { EditUserComponent } from './admin/index';
import { UserprofileComponent } from './admin/index';
import { reportComponent } from './report/index';
import { holidayCalendarComponent } from './holiday_calendar/index';
import { CSVUploadComponent } from './file_upload/index';


const appRoutes: Routes = [
    { path: '', component: HomeComponent, canActivate: [AuthGuard] },
    { path: 'login', component: LoginComponent },
    { path: 'register', component: RegisterComponent },
	{ path: 'editUser/:id', component: EditUserComponent },
	{ path: 'Profileuser/:id', component: UserprofileComponent },
	{ path: 'uploadCSV', component: CSVUploadComponent, canActivate: [AuthGuard] },
	{ path: 'report', component: reportComponent},
	{ path: 'holidayCalendar', component: holidayCalendarComponent },
	// otherwise redirect to home
    { path: '**', redirectTo: '' }
];

export const routing = RouterModule.forRoot(appRoutes);