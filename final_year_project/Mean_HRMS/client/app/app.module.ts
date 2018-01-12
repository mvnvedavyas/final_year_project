import { NgModule } from '@angular/core';
import { BrowserModule } from '@angular/platform-browser';
import { FormsModule } from '@angular/forms';
import { HttpModule } from '@angular/http'; 
import { MyDatePickerModule } from 'mydatepicker';

import { AppComponent } from './app.component';
import { routing } from './app.routing';
import { AppConfig } from './app.config';

import { AlertComponent } from './_directives/index';
import { AuthGuard } from './_guards/index';
import { AlertService, AuthenticationService, UserService, HolidayService, ReportService } from './_services/index';
import { HomeComponent } from './home/index';
import { UserListComponent } from './home/index';
import { AdminComponent } from './admin/index'
import { LoginComponent } from './login/index';
import { RegisterComponent } from './register/index';
import { EditUserComponent } from './admin/index';
import { AddEmployeeComponent } from './admin/index';
import { CSVUploadComponent } from './file_upload/index';
import { UserprofileComponent } from './admin/index';
import { reportComponent } from './report/index';
import { holidayCalendarComponent } from './holiday_calendar/index';

import { FileSelectDirective, FileDropDirective, FileUploader } from 'ng2-file-upload';

@NgModule({
    imports: [
        BrowserModule,
        FormsModule,
        HttpModule, 
        routing,
        MyDatePickerModule
    ],
    declarations: [
        AppComponent,
        AlertComponent,
        HomeComponent,
		UserListComponent,
        LoginComponent,
        RegisterComponent,
		AdminComponent,
		EditUserComponent,
		AddEmployeeComponent,
		CSVUploadComponent,
        UserprofileComponent,
        reportComponent,
        holidayCalendarComponent,
        FileSelectDirective,
      	FileDropDirective
    ],
    providers: [
        AppConfig,
        AuthGuard,
        AlertService,
        AuthenticationService,
        UserService,
        HolidayService,
        ReportService
    ],
    bootstrap: [AppComponent]
})

export class AppModule { }